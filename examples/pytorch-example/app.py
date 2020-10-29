import fret

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision.datasets import MNIST
from torchvision.transforms import ToTensor
from sklearn.metrics import precision_recall_fscore_support

from tqdm import tqdm


class PyTorchRuntime(fret.Runtime):
    def save(self, obj, fn):
        torch.save(obj, fn)

    def load(self, fn):
        return torch.load(fn)


fret.set_runtime_class(PyTorchRuntime)


@fret.configurable
class CNN(nn.Module):
    def __init__(self, n_classes, feature_maps=[4, 8, 16, 32, 64]):
        super().__init__()
        assert len(feature_maps) == 5
        self.act = nn.ReLU()
        self.feature = nn.Sequential(
            nn.Conv2d(1, 4, 3), self.act,
            nn.Conv2d(feature_maps[0], feature_maps[1], 3), self.act,
            nn.MaxPool2d(2),
            nn.Conv2d(feature_maps[1], feature_maps[2], 3), self.act,
            nn.Conv2d(feature_maps[2], feature_maps[3], 3), self.act,
            nn.MaxPool2d(2),
            nn.Conv2d(feature_maps[3], feature_maps[4], 3), self.act,
            nn.MaxPool2d(2)
        )
        self.out = nn.Linear(feature_maps[4], n_classes)

    def forward(self, x):
        x = self.feature(x.unsqueeze(1).float() / 255.)
        x = x.mean(dim=-1).mean(dim=-1)
        return self.out(x)


@fret.command
def check(ws):
    model = ws.build(n_classes=5)
    print(model)


@fret.command
def train(ws, n_epochs=5, batch_size=64):
    logger = ws.logger('train')

    data, _ = load_data(False)
    model = ws.build(n_classes=10)
    model.train()

    optimizer = torch.optim.Adam(model.parameters())

    with ws.run('train') as run:
        run.register(model)
        run.register(optimizer)
        for i in run.brange(n_epochs):
            total_loss = run.acc(name='total_loss')
            train_iter = run.iter(data.train_data,
                                  data.train_labels,
                                  prefetch=True, batch_size=batch_size,
                                  name='train_iter')
            for batch in fret.nonbreak(tqdm(train_iter,
                                            initial=train_iter.pos)):
                y_pred = model(batch[0])
                loss = F.cross_entropy(y_pred, batch[1])
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                total_loss += loss.item()

            logger.info('epoch: %d, loss: %.4f', i, total_loss.mean())
            ws.save(model, str(i))


@fret.command
def test(ws, epoch, batch_size=128):
    model = ws.load(tag=str(epoch))
    model.eval()

    _, data = load_data(False)

    with torch.no_grad():
        preds = []
        trues = []
        test_iter = fret.util.Iterator(data.test_data, data.test_labels,
                                       prefetch=True, batch_size=batch_size)
        for batch in tqdm(test_iter):
            y_pred = model(batch[0])
            y_pred = y_pred.max(dim=1)[1]
            y_true = batch[1]
            preds.append(y_pred)
            trues.append(y_true)

        preds = torch.cat(preds)
        trues = torch.cat(trues)

    return precision_recall_fscore_support(preds, trues, average='weighted')


@fret.command
def load_data(download=True):
    train_data = MNIST('./data/', download=True, transform=ToTensor())
    test_data = MNIST('./data/', train=False, download=True,
                      transform=ToTensor())
    return train_data, test_data
