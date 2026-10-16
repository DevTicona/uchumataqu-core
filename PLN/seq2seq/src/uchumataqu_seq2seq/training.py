import random
import time

import torch
from torch.nn import functional as F

from .data import ROOT, Codec, digest, write
from .evaluation import baseline_report, evaluate
from .model import Seq2Seq


def batches(records, codec, batch_size, rng):
    shuffled = list(records)
    rng.shuffle(shuffled)
    for start in range(0, len(shuffled), batch_size):
        batch = shuffled[start:start + batch_size]
        targets = [codec.target(record) for record in batch]
        width = max(map(len, targets))
        yield (torch.tensor([codec.encode(r['surface']) for r in batch]),
               torch.tensor([target + [0] * (width - len(target)) for target in targets]))


def load_checkpoint(path):
    checkpoint = torch.load(path, map_location='cpu', weights_only=True)
    model = Seq2Seq(checkpoint['vocab'], checkpoint['config'])
    model.load_state_dict(checkpoint['weights'])
    model.eval()
    return model, checkpoint


def train(dataset, config):
    torch.set_num_threads(config['threads'])
    torch.use_deterministic_algorithms(True)
    codec = Codec(dataset['vocab'], config)
    parts = {name: [r for r in dataset['records'] if r['id'] in ids] for name, ids in dataset['splits'].items()}
    summaries = []
    for seed in config['seeds']:
        folder = ROOT / f'runs/seed-{seed}'
        folder.mkdir(parents=True, exist_ok=True)
        torch.manual_seed(seed)
        rng = random.Random(seed)
        model = Seq2Seq(dataset['vocab'], config)
        optimizer = torch.optim.Adam(model.parameters(), lr=config['learning_rate'])
        best, stale, history = (-1.0, -1.0), 0, []
        started = time.monotonic()
        for epoch in range(1, config['epochs'] + 1):
            model.train()
            total, count = 0.0, 0
            for ids, targets in batches(parts['train'], codec, config['batch_size'], rng):
                optimizer.zero_grad(set_to_none=True)
                logits = model(ids, targets)
                loss = F.cross_entropy(logits.reshape(-1, logits.shape[-1]), targets.reshape(-1), ignore_index=0)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                total += loss.item()
                count += 1
            if epoch % config['eval_every'] and epoch != config['epochs']:
                continue
            metrics, _ = evaluate(model, parts['dev'], codec)
            score = (metrics['exact'], metrics['lemma_exact'])
            row = {'epoch': epoch, 'train_loss': total / count, 'dev': metrics}
            history.append(row)
            write(folder / 'history.json', history)
            if score > best:
                best, stale = score, 0
                torch.save({'weights': model.state_dict(), 'vocab': dataset['vocab'], 'config': config,
                            'seed': seed, 'epoch': epoch, 'dev': metrics,
                            'dataset_sha256': digest(ROOT / 'data/prepared/dataset.json')}, folder / 'best.pt')
            else:
                stale += 1
            print(f"seed={seed} epoch={epoch} loss={total/count:.4f} dev_exact={metrics['exact']:.3f}", flush=True)
            if stale >= config['patience']:
                break
        _, checkpoint = load_checkpoint(folder / 'best.pt')
        summaries.append({'seed': seed, 'best_epoch': checkpoint['epoch'], 'dev': checkpoint['dev'],
                          'seconds': time.monotonic() - started})
    selected = max(summaries, key=lambda row: (row['dev']['exact'], row['dev']['lemma_exact']))
    model, checkpoint = load_checkpoint(ROOT / f"runs/seed-{selected['seed']}/best.pt")
    # El conjunto de prueba se abre solo después de seleccionar con desarrollo.
    test_metrics, predictions = evaluate(model, parts['test'], codec)
    train_metrics, _ = evaluate(model, parts['train'], codec)
    torch.save(checkpoint, ROOT / 'runs/selected.pt')
    report = {'experiment': 'exploratory_unreviewed_targets', 'seeds': summaries, 'selected_seed': selected['seed'],
              'train': train_metrics, 'test': test_metrics, 'baseline': baseline_report(parts['train'], parts['test']),
              'parameters': sum(p.numel() for p in model.parameters()),
              'deployment_allowed': False, 'reason': 'Falta revisión lingüística, evaluación educativa y validación Sentis/Android.'}
    write(ROOT / 'reports/experiment.json', report)
    write(ROOT / 'reports/test-predictions.json', predictions)
    return report
