import torch
from torch import nn


class Encoder(nn.Module):
    def __init__(self, vocabulary, embedding, hidden):
        super().__init__()
        self.embedding = nn.Embedding(vocabulary, embedding, padding_idx=0)
        self.gru = nn.GRU(embedding, hidden, batch_first=True)

    def forward(self, ids, mask):
        memory, _ = self.gru(self.embedding(ids))
        index = (mask.sum(dim=1).long() - 1).clamp(min=0)
        state = memory.gather(1, index[:, None, None].expand(-1, 1, memory.shape[2])).squeeze(1)
        return memory, state


class Decoder(nn.Module):
    def __init__(self, vocabulary, embedding, hidden):
        super().__init__()
        self.embedding = nn.Embedding(vocabulary, embedding, padding_idx=0)
        self.query = nn.Linear(hidden, hidden, bias=False)
        self.gru = nn.GRUCell(embedding + hidden, hidden)
        self.output = nn.Linear(hidden * 2, vocabulary)

    def forward(self, previous, state, memory, mask):
        scores = torch.bmm(memory, self.query(state).unsqueeze(2)).squeeze(2)
        scores = scores.masked_fill(mask == 0, -1e4)
        context = torch.bmm(torch.softmax(scores, dim=1).unsqueeze(1), memory).squeeze(1)
        state = self.gru(torch.cat([self.embedding(previous), context], dim=1), state)
        return self.output(torch.cat([state, context], dim=1)), state


class Seq2Seq(nn.Module):
    def __init__(self, vocab, config):
        super().__init__()
        self.encoder = Encoder(len(vocab['input']), config['embedding'], config['hidden'])
        self.decoder = Decoder(len(vocab['output']), config['embedding'], config['hidden'])

    def forward(self, ids, targets):
        mask = (ids != 0).float()
        memory, state = self.encoder(ids, mask)
        previous = torch.full((ids.shape[0],), 2, dtype=torch.long, device=ids.device)
        outputs = []
        for step in range(targets.shape[1]):
            logits, state = self.decoder(previous, state, memory, mask)
            outputs.append(logits)
            previous = targets[:, step]
        return torch.stack(outputs, dim=1)

    @torch.inference_mode()
    def generate(self, ids, max_output):
        mask = (ids != 0).float()
        memory, state = self.encoder(ids, mask)
        previous = torch.full((ids.shape[0],), 2, dtype=torch.long, device=ids.device)
        finished = torch.zeros(ids.shape[0], dtype=torch.bool, device=ids.device)
        outputs = []
        for _ in range(max_output):
            logits, state = self.decoder(previous, state, memory, mask)
            logits[:, :3] = -1e4
            previous = logits.argmax(dim=1)
            outputs.append(previous)
            finished |= previous == 3
            if finished.all():
                break
        return torch.stack(outputs, dim=1).tolist()
