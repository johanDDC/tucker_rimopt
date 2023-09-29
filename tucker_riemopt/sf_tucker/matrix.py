from string import ascii_letters
from dataclasses import dataclass
from typing import Sequence, Union

from tucker_riemopt import backend as back
from tucker_riemopt import SFTucker


@dataclass()
class SFTuckerMatrix(SFTucker):
    n: Union[Sequence[int], None] = None
    m: Union[Sequence[int], None] = None

    @classmethod
    def from_dense(cls, T: back.type(), ds: Union[int, None] = None, n: Union[Sequence[int], None] = None,
                   m: Union[Sequence[int], None] = None,
                   eps=1e-14):
        if n is None or m is None:
            raise ValueError("n and m parameter must be specialized for matrices")
        T = super().from_dense(T, ds, eps)
        return cls(T.core, T.regular_factors[:T.dt], T.ds, T.shared_factor, n, m)

    def __matmul__(self, other: Union[back.type(), SFTucker, "SFTuckerMatrix"]):
        """
        Performs matrix multiplication of tensors. If other's ndim > matrix ndim, then performs batch matmul over last
        ndim modes.

        :param other: can be dense tensor, SFTucker or SFTuckerMatrix. If dense tensor, then treated as vector and matvec
        operation is performed. The result is also a dense tensor. If `SFTucker`, then treated as vector and matvec
        operation is performed. The result is also a SFTucker. Else matmul operation is performed and another matrix is
        returned.

        :return: dense tensor, SFTucker or SFTuckerMatrix, depends on type of `other`.
        """
        if type(other) == back.type():
            core_letters = ascii_letters[:self.ndim]
            factors_letters = []
            operand_letters = []
            result_letters = []
            reshaped_factors = []
            for i in range(self.ndim):
                if i < self.dt:
                    reshaped_factors.append(back.reshape(self.factors[i], (self.n[i], self.m[i], -1), order="F"))
                factors_letters.append(ascii_letters[self.ndim + 2 * i: self.ndim + 2 * (i + 1)] + core_letters[i])
                operand_letters.append(factors_letters[-1][0])
                result_letters.append(factors_letters[-1][1])
            reshaped_shared_factor = back.reshape(self.shared_factor, (self.n[-1], self.m[-1], -1), order="F")
            batch_letters = []
            for i in range(len(other.shape) - self.ndim):
                batch_letters.append(ascii_letters[2 * (self.ndim + 1) + i + 1])
            operand_letters = batch_letters + operand_letters
            result_letters = batch_letters + result_letters
            return back.einsum(
                f"{core_letters},{','.join(factors_letters)},{''.join(operand_letters)}->{''.join(result_letters)}",
                self.core, *reshaped_factors, *([reshaped_shared_factor] * self.ds), other)