import warnings
from distutils.version import LooseVersion

try:
    import torch
except ImportError as error:
    message = ("Impossible to import PyTorch.\n"
               "To use Tucker riemopt with the PyTorch backend, "
               "you must first install PyTorch!")
    raise ImportError(message) from error

import numpy as np
import typing
from .backend import Backend

linalg_lstsq_avail = LooseVersion(torch.__version__) >= LooseVersion("1.9.0")


class PyTorchBackend(Backend, backend_name="pytorch"):
    @property
    def type(self):
        return type(self.tensor([]))

    @staticmethod
    def context(tensor):
        return {"dtype": tensor.dtype,
                "device": tensor.device,
                "requires_grad": tensor.requires_grad}

    @staticmethod
    def tensor(data, dtype=torch.float32, device="cpu", requires_grad=False):
        if isinstance(data, np.ndarray):
            data = data.copy()
        return torch.tensor(data, dtype=dtype, device=device, requires_grad=requires_grad)

    @staticmethod
    def to_numpy(tensor):
        if torch.is_tensor(tensor):
            if tensor.requires_grad:
                tensor = tensor.detach()
            if tensor.cuda:
                tensor = tensor.cpu()
            return tensor.numpy()
        elif isinstance(tensor, np.ndarray):
            return tensor
        else:
            return np.asarray(tensor)

    @staticmethod
    def shape(tensor):
        return tensor.shape

    @staticmethod
    def ndim(tensor):
        return tensor.dim()

    @staticmethod
    def arange(start, stop=None, step=1.0, *args, **kwargs):
        if stop is None:
            return torch.arange(start=0., end=float(start), step=float(step), *args, **kwargs)
        else:
            return torch.arange(float(start), float(stop), float(step), *args, **kwargs)

    @staticmethod
    def reshape(tensor, newshape, order="C"):
        def reshape_fortran(x, shape):
            if len(x.shape) > 0:
                x = x.permute(*reversed(range(len(x.shape))))
            return x.reshape(*reversed(shape)).permute(*reversed(range(len(shape))))

        if order == "C":
            return torch.reshape(tensor, newshape)
        elif order == "F":
            return reshape_fortran(tensor, newshape)
        else:
            raise NotImplementedError("Only C-style and Fortran-style reshapes are supported")

    @staticmethod
    def clip(tensor, a_min=None, a_max=None, inplace=False):
        if a_max is None:
            a_max = torch.max(tensor)
        if a_min is None:
            a_min = torch.min(tensor)
        if inplace:
            return torch.clamp(tensor, a_min, a_max, out=tensor)
        else:
            return torch.clamp(tensor, a_min, a_max)

    @staticmethod
    def all(tensor):
        return torch.sum(tensor != 0)

    def transpose(self, tensor, axes=None):
        axes = axes or list(range(self.ndim(tensor)))[::-1]
        return tensor.permute(*axes)

    @staticmethod
    def copy(tensor):
        return tensor.clone()

    @staticmethod
    def norm(tensor, order=None, axis=None):
        kwds = {}
        if axis is not None:
            kwds["dim"] = axis
        if order and order != "inf":
            kwds["p"] = order

        if order == "inf":
            res = torch.max(torch.abs(tensor), **kwds)
            if axis is not None:
                return res[0]  # ignore indices output
            return res
        return torch.norm(tensor, **kwds)

    @staticmethod
    def dot(a, b):
        if a.ndim > 2 and b.ndim > 2:
            return torch.tensordot(a, b, dims=([-1], [-2]))
        if not a.ndim or not b.ndim:
            return a * b
        return torch.matmul(a, b)

    @staticmethod
    def mean(tensor, axis=None):
        if axis is None:
            return torch.mean(tensor)
        else:
            return torch.mean(tensor, dim=axis)

    @staticmethod
    def sum(tensor, axis=None):
        if axis is None:
            return torch.sum(tensor)
        else:
            return torch.sum(tensor, dim=axis)

    @staticmethod
    def max(tensor, axis=None):
        if axis is None:
            return torch.max(tensor)
        else:
            return torch.max(tensor, dim=axis)[0]

    @staticmethod
    def flip(tensor, axis=None):
        if isinstance(axis, int):
            axis = [axis]

        if axis is None:
            return torch.flip(tensor, dims=[i for i in range(tensor.ndim)])
        else:
            return torch.flip(tensor, dims=axis)

    @staticmethod
    def concatenate(tensors, axis=0):
        return torch.cat(tensors, dim=axis)

    @staticmethod
    def argmin(input, axis=None):
        return torch.argmin(input, dim=axis)

    @staticmethod
    def argsort(input, axis=None, descending=False):
        return torch.argsort(input, dim=axis, descending=descending)

    @staticmethod
    def argmax(input, axis=None):
        return torch.argmax(input, dim=axis)

    @staticmethod
    def stack(arrays, axis=0):
        return torch.stack(arrays, dim=axis)

    @staticmethod
    def diag(tensor, k=0):
        return torch.diag(tensor, diagonal=k)

    @staticmethod
    def sort(tensor, axis, descending=False):
        if axis is None:
            tensor = tensor.flatten()
            axis = -1

        return torch.sort(tensor, dim=axis, descending=descending).values

    @staticmethod
    def update_index(tensor, index, values):
        tensor.index_put_(index, values)

    def solve(self, matrix1, matrix2):
        if self.ndim(matrix2) < 2:
            solution, _ = torch.solve(matrix2.unsqueeze(1), matrix1)
        else:
            solution, _ = torch.solve(matrix2, matrix1)
        return solution

    @staticmethod
    def lstsq(a, b):
        if linalg_lstsq_avail:
            x, residuals, _, _ = torch.linalg.lstsq(a, b, rcond=None, driver="gelsd")
            return x, residuals
        else:
            n = a.shape[1]
            sol = torch.lstsq(b, a)[0]
            x = sol[:n]
            residuals = torch.norm(sol[n:], dim=0) ** 2
            return x, residuals if torch.matrix_rank(a) == n else torch.tensor([], device=x.device)

    @staticmethod
    def eigh(tensor):
        return torch.symeig(tensor, eigenvectors=True)

    @staticmethod
    def svd(matrix, full_matrices=True):
        some = not full_matrices
        u, s, v = torch.svd(matrix, some=some, compute_uv=True)
        return u, s, v.transpose(-2, -1).conj()

    @staticmethod
    def cumsum(tensor, axis=None):
        return torch.cumsum(tensor, dim=-1 if axis is None else axis)

    @staticmethod
    def grad(func: typing.Callable, argnums: typing.Union[int, typing.Sequence[int]] = 0):
        def aux_func(*args):
            func(args).backward()
            if type(argnums) is int:
                return args[argnums].grad
            else:
                grads = []
                for arg in argnums:
                    grads.append(args[arg].grad)
                return grads

        return aux_func

    @staticmethod
    def pad(tensor, pad_width, constant_values):
        from torch.nn.functional import pad
        flat_pad_width = []
        for pair in pad_width:
            flat_pad_width.append(pair[0])
            flat_pad_width.append(pair[1])
        flat_pad_width = flat_pad_width[::-1]
        return pad(tensor, flat_pad_width, "constant", 0)


# Register the other functions
for name in ["float64", "float32", "int64", "int32", "complex128", "complex64",
             "is_tensor", "ones", "zeros", "any", "trace", "count_nonzero",
             "zeros_like", "eye", "min", "prod", "abs", "matmul",
             "sqrt", "sign", "where", "conj", "finfo", "einsum", "log2", "sin", "cos", "squeeze"]:
    PyTorchBackend.register_method(name, getattr(torch, name))

# PyTorch 1.8.0 has a much better NumPy interface but somoe haven"t updated yet
if LooseVersion(torch.__version__) < LooseVersion("1.8.0"):
    warnings.warn(f"You are using an old version of PyTorch ({torch.__version__}). "
                  "We recommend upgrading to a newest one, e.g. >1.8.0.")
    PyTorchBackend.register_method("qr", getattr(torch, "qr"))

else:
    # New PyTorch NumPy interface
    for name in ["kron"]:
        PyTorchBackend.register_method(name, getattr(torch, name))

    for name in ["solve", "qr", "svd", "eigh"]:
        PyTorchBackend.register_method(name, getattr(torch.linalg, name))