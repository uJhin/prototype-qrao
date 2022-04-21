# This code is part of Qiskit.
#
# (C) Copyright IBM 2022.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Test that the encoded Hamiltonian commutes as expected"""

import pytest

import numpy as np

from docplex.mp.model import Model
from qiskit.opflow import StateFn

from qiskit_optimization.translators import from_docplex_mp
from qiskit_optimization.problems.quadratic_program import QuadraticProgram

from qrao import QuantumRandomAccessEncoding

# Corresponds to the "check encoding problem commutation" how-to notebook


def check_encoding_problem_commutation(
    encoding: QuantumRandomAccessEncoding, verbose=False
):
    if not encoding.num_vars:
        raise ValueError("Empty encoding passed to check_encoding_problem_commutation")

    problem = encoding.problem
    encoded_problem = encoding.qubit_op  # H
    # print(problem)

    # Offset accounts for the value of the encoded Hamiltonian's
    # identity coefficient. This term need not be evaluated directly as
    # Tr[I•rho] is always 1.
    offset = encoding.offset
    if verbose:
        print("Encoded Problem:\n=================")
        print(encoded_problem)
        print(f"Offset = {offset}")
        print("{qubit : dvars} = ", encoding.q2vars)
        print("")

    violations = {}
    non_violations = {}
    for i in range(2**encoding.num_vars):
        str_dvars = ("{0:0" + str(encoding.num_vars) + "b}").format(i)
        dvars = [int(b) for b in str_dvars]
        encoded_bitstr = encoding.state_prep(dvars)

        # Evaluate Un-encoded Problem
        # ========================
        # `sense` accounts for sign flips depending on whether
        # we are minimizing or maximizing the objective function
        sense = problem.objective.sense.value
        obj_val = problem.objective.evaluate(dvars) * sense

        # Evaluate Encoded Problem
        # ========================
        encoded_obj_val = (
            np.real((~StateFn(encoded_problem) @ encoded_bitstr).eval()) + offset
        )

        if np.isclose(obj_val, encoded_obj_val):
            non_violations.update({str_dvars: (obj_val, encoded_obj_val)})
        else:
            violations.update({str_dvars: (obj_val, encoded_obj_val)})
    return violations, non_violations, offset


def check_problem_commutation(problem: QuadraticProgram, max_vars_per_qubit: int):
    encoding = QuantumRandomAccessEncoding(max_vars_per_qubit=max_vars_per_qubit)
    encoding.encode(problem)
    violations, non_violations, _ = check_encoding_problem_commutation(encoding)
    assert len(violations) + len(non_violations) == 2**encoding.num_vars
    assert len(violations) == 0


@pytest.mark.parametrize("max_vars_per_qubit", [1, 2, 3])
@pytest.mark.parametrize("task", ["minimize", "maximize"])
def test_one_qubit_qrac(max_vars_per_qubit, task):
    """Non-uniform weights, degree 1 terms"""
    mod = Model("maxcut")
    num_nodes = max_vars_per_qubit
    nodes = list(range(num_nodes))
    var = [mod.binary_var(name="x" + str(i)) for i in nodes]
    {"minimize": mod.minimize, "maximize": mod.maximize}[task](
        mod.sum(2 * (i + 1) * var[i] for i in nodes)
    )
    problem = from_docplex_mp(mod)

    check_problem_commutation(problem, max_vars_per_qubit=max_vars_per_qubit)