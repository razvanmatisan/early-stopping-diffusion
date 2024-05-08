import random
import numpy as np
import time
import torch
from typing import Sequence
from torch.utils.data import DataLoader
from diffusers.optimization import get_cosine_schedule_with_warmup

from datasets.cifar10 import get_cifar10_dataloader
from datasets.celeba import get_celeba_dataloader
from models.uvit import UViT
from ddpm_core import NoiseScheduler


def get_model(args):
    if args.model == "uvit":
        return UViT(
            img_size=args.img_size,
            patch_size=args.patch_size,
            embed_dim=args.embed_dim,
            depth=args.depth,
            num_heads=args.num_heads,
            mlp_ratio=args.mlp_ratio,
            qkv_bias=args.qkv_bias,
            mlp_time_embed=args.mlp_time_embed,
            num_classes=args.num_classes,
        )


def get_optimizer(model, args):
    if args.optimizer == "adamw":
        return torch.optim.AdamW(
            model.parameters(),
            lr=args.lr,
            betas=(args.beta1, args.beta2),
            weight_decay=args.weight_decay,
        )


def get_dataloader(args):
    if args.dataset == "cifar10":
        return get_cifar10_dataloader(batch_size=args.batch_size)
    elif args.adataset == "celeba":
        return get_celeba_dataloader(batch_size=args.batch_size)


def get_noise_scheduler(args):
    return NoiseScheduler(beta_steps=args.num_train_timesteps)


def get_lr_scheduler(optimizer, args):
    return get_cosine_schedule_with_warmup(
        optimizer=optimizer,
        num_warmup_steps=args.num_warmup_steps,
        num_training_steps=args.n_steps,
    )


# https://github.com/open-mmlab/mmengine/blob/main/mmengine/runner/loops.py
class InfiniteDataloaderIterator:
    """An infinite dataloader iterator wrapper for IterBasedTrainLoop.

    It resets the dataloader to continue iterating when the iterator has
    iterated over all the data. However, this approach is not efficient, as the
    workers need to be restarted every time the dataloader is reset. It is
    recommended to use `mmengine.dataset.InfiniteSampler` to enable the
    dataloader to iterate infinitely.
    """

    def __init__(self, dataloader: DataLoader) -> None:
        self._dataloader = dataloader
        self._iterator = iter(self._dataloader)
        self._epoch = 0

    def __iter__(self):
        return self

    def __next__(self) -> Sequence[dict]:
        try:
            data = next(self._iterator)
        except StopIteration:
            self._epoch += 1
            if hasattr(self._dataloader, "sampler") and hasattr(
                self._dataloader.sampler, "set_epoch"
            ):
                # In case the` _SingleProcessDataLoaderIter` has no sampler,
                # or data loader uses `SequentialSampler` in Pytorch.
                self._dataloader.sampler.set_epoch(self._epoch)

            elif hasattr(self._dataloader, "batch_sampler") and hasattr(
                self._dataloader.batch_sampler.sampler, "set_epoch"
            ):
                # In case the` _SingleProcessDataLoaderIter` has no batch
                # sampler. batch sampler in pytorch warps the sampler as its
                # attributes.
                self._dataloader.batch_sampler.sampler.set_epoch(self._epoch)
            time.sleep(2)  # Prevent possible deadlock during epoch transition
            self._iterator = iter(self._dataloader)
            data = next(self._iterator)
        return data


def seed_everything(seed):
    torch.manual_seed(seed)
    random.seed(seed)
    np.random.seed(seed)