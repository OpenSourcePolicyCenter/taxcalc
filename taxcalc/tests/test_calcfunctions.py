"""
Tests for Tax-Calculator calcfunctions.py logic.
"""
# CODING-STYLE CHECKS:
# pycodestyle test_calcfunctions.py
# pylint --disable=locally-disabled test_calcfunctions.py

import os
import re
import ast
from taxcalc import Records  # pylint: disable=import-error
from taxcalc import calcfunctions
import numpy as np
import pytest


class GetFuncDefs(ast.NodeVisitor):
    """
    Return information about each function defined in the functions.py file.
    """
    def __init__(self):
        """
        GetFuncDefs class constructor
        """
        self.fname = ''
        self.fnames = list()  # function name (fname) list
        self.fargs = dict()  # lists of function arguments indexed by fname
        self.cvars = dict()  # lists of calc vars in function indexed by fname
        self.rvars = dict()  # lists of function return vars indexed by fname

    def visit_Module(self, node):  # pylint: disable=invalid-name
        """
        visit the specified Module node
        """
        self.generic_visit(node)
        return (self.fnames, self.fargs, self.cvars, self.rvars)

    def visit_FunctionDef(self, node):  # pylint: disable=invalid-name
        """
        visit the specified FunctionDef node
        """
        self.fname = node.name
        self.fnames.append(self.fname)
        self.fargs[self.fname] = list()
        for anode in ast.iter_child_nodes(node.args):
            self.fargs[self.fname].append(anode.arg)
        self.cvars[self.fname] = list()
        for bodynode in node.body:
            if isinstance(bodynode, ast.Return):
                continue  # skip function's Return node
            for bnode in ast.walk(bodynode):
                if isinstance(bnode, ast.Name):
                    if isinstance(bnode.ctx, ast.Store):
                        if bnode.id not in self.cvars[self.fname]:
                            self.cvars[self.fname].append(bnode.id)
        self.generic_visit(node)

    def visit_Return(self, node):  # pylint: disable=invalid-name
        """
        visit the specified Return node
        """
        if isinstance(node.value, ast.Tuple):
            self.rvars[self.fname] = [r_v.id for r_v in node.value.elts]
        elif isinstance(node.value, ast.BinOp):
            self.rvars[self.fname] = []  # no vars returned; only an expression
        else:
            self.rvars[self.fname] = [node.value.id]
        self.generic_visit(node)


def test_calc_and_used_vars(tests_path):
    """
    Runs two kinds of tests on variables used in the calcfunctions.py file:

    (1) Checks that each var in Records.CALCULATED_VARS is actually calculated

    If test (1) fails, a variable in Records.CALCULATED_VARS was not
    calculated in any function in the calcfunctions.py file.  With the
    exception of a few variables listed in this test, all
    Records.CALCULATED_VARS must be calculated in the calcfunctions.py file.

    (2) Check that each variable that is calculated in a function and
    returned by that function is an argument of that function.
    """
    # pylint: disable=too-many-locals
    funcpath = os.path.join(tests_path, '..', 'calcfunctions.py')
    gfd = GetFuncDefs()
    fnames, fargs, cvars, rvars = gfd.visit(ast.parse(open(funcpath).read()))
    # Test (1):
    # .. create set of vars that are actually calculated in calcfunctions.py
    all_cvars = set()
    for fname in fnames:
        if fname == 'BenefitSurtax':
            continue  # because BenefitSurtax is not really a function
        all_cvars.update(set(cvars[fname]))
    # .. add to all_cvars set variables calculated in Records class
    all_cvars.update(set(['num', 'sep', 'exact']))
    # .. add to all_cvars set variables calculated elsewhere
    all_cvars.update(set(['mtr_paytax', 'mtr_inctax']))
    all_cvars.update(set(['benefit_cost_total', 'benefit_value_total']))
    # .. check that each var in Records.CALCULATED_VARS is in the all_cvars set
    records_varinfo = Records(data=None)
    found_error1 = False
    if not records_varinfo.CALCULATED_VARS <= all_cvars:
        msg1 = ('all Records.CALCULATED_VARS not calculated '
                'in calcfunctions.py\n')
        for var in records_varinfo.CALCULATED_VARS - all_cvars:
            found_error1 = True
            msg1 += 'VAR NOT CALCULATED: {}\n'.format(var)
    # Test (2):
    faux_functions = ['EITCamount', 'ComputeBenefit', 'BenefitPrograms',
                      'BenefitSurtax', 'BenefitLimitation']
    found_error2 = False
    msg2 = 'calculated & returned variables are not function arguments\n'
    for fname in fnames:
        if fname in faux_functions:
            continue  # because fname is not a genuine function
        crvars_set = set(cvars[fname]) & set(rvars[fname])
        if not crvars_set <= set(fargs[fname]):
            found_error2 = True
            for var in crvars_set - set(fargs[fname]):
                msg2 += 'FUNCTION,VARIABLE: {} {}\n'.format(fname, var)
    # Report errors for the two tests:
    if found_error1 and found_error2:
        raise ValueError('{}\n{}'.format(msg1, msg2))
    if found_error1:
        raise ValueError(msg1)
    if found_error2:
        raise ValueError(msg2)


def test_function_args_usage(tests_path):
    """
    Checks each function argument in calcfunctions.py for use in its
    function body.
    """
    funcfilename = os.path.join(tests_path, '..', 'calcfunctions.py')
    with open(funcfilename, 'r') as funcfile:
        fcontent = funcfile.read()
    fcontent = re.sub('#.*', '', fcontent)  # remove all '#...' comments
    fcontent = re.sub('\n', ' ', fcontent)  # replace EOL character with space
    funcs = fcontent.split('def ')  # list of function text
    msg = 'FUNCTION ARGUMENT(S) NEVER USED:\n'
    found_error = False
    for func in funcs[1:]:  # skip first item in list, which is imports, etc.
        fcode = func.split('return ')[0]  # fcode is between def and return
        match = re.search(r'^(.+?)\((.*?)\):(.*)$', fcode)
        if match is None:
            msg = ('Could not find function name, arguments, '
                   'and code portions in the following text:\n')
            msg += '--------------------------------------------------------\n'
            msg += '{}\n'.format(fcode)
            msg += '--------------------------------------------------------\n'
            raise ValueError(msg)
        fname = match.group(1)
        fargs = match.group(2).split(',')  # list of function arguments
        fbody = match.group(3)
        if fname == 'Taxes':
            continue  # because Taxes has part of fbody in return statement
        for farg in fargs:
            arg = farg.strip()
            if fbody.find(arg) < 0:
                found_error = True
                msg += 'FUNCTION,ARGUMENT= {} {}\n'.format(fname, arg)
    if found_error:
        raise ValueError(msg)


def test_DependentCare(skip_jit):
    """
    Tests the DependentCare function
    """

    test_tuple = (3, 2, 100000, 1, [250000, 500000, 250000, 500000, 250000],
                  .2, 7165, 5000, 0)
    test_value = calcfunctions.DependentCare(*test_tuple)
    expected_value = 25196

    assert np.allclose(test_value, expected_value)


STD_in = [6000, 12000, 6000, 12000, 12000]
STD_Aged_in = [1500, 1200, 1500, 1500, 1500]
tuple1 = (0, 1000, STD_in, 45, 44, STD_Aged_in, 1000, 2, 0, 0, 0, 2, 0,
          False, 0)
tuple2 = (0, 1000, STD_in, 66, 44, STD_Aged_in, 1000, 2, 0, 1, 1, 2,
          200, True, 300)
tuple3 = (0, 1000, STD_in, 44, 66, STD_Aged_in, 1000, 2, 0, 0, 0, 2,
          400, True, 300)
tuple4 = (0, 1200, STD_in, 66, 67, STD_Aged_in, 1000, 2, 0, 0, 0, 2, 0,
          True, 0)
tuple5 = (0, 1000, STD_in, 44, 0, STD_Aged_in, 1000, 1, 0, 0, 0, 2, 0,
          True, 0)
tuple6 = (0, 1000, STD_in, 44, 0, STD_Aged_in, 1000, 1, 0, 0, 0, 2, 0,
          True, 0)
tuple7 = (0, 1000, STD_in, 44, 0, STD_Aged_in, 1000, 3, 1, 0, 0, 2, 0,
          True, 0)
tuple8 = (1, 200, STD_in, 44, 0, STD_Aged_in, 1000, 3, 0, 0, 0, 2, 0,
          True, 0)
tuple9 = (1, 1000, STD_in, 44, 0, STD_Aged_in, 1000, 3, 0, 0, 0, 2, 0,
          True, 0)
expected = [12000, 15800, 13500, 14400, 6000, 6000, 0, 1000, 1350]


@pytest.mark.parametrize(
    'test_tuple,expected_value', [
        (tuple1, expected[0]), (tuple2, expected[1]),
        (tuple3, expected[2]), (tuple4, expected[3]),
        (tuple5, expected[4]), (tuple6, expected[5]),
        (tuple7, expected[6]), (tuple8, expected[7]),
        (tuple9, expected[8])], ids=[
            'Married, young', 'Married, allow charity',
            'Married, allow charity, over limit',
            'Married, two old', 'Single 1', 'Single 2', 'Married, Single',
            'Marrid, Single, dep, under earn',
            'Married, Single, dep, over earn'])
def test_StdDed(test_tuple, expected_value, skip_jit):
    """
    Tests the StdDed function
    """
    test_value = calcfunctions.StdDed(*test_tuple)

    assert np.allclose(test_value, expected_value)


def test_AfterTaxIncome(skip_jit):
    '''
    Tests the AfterTaxIncome function
    '''
    test_tuple = (1000, 5000, 4000)
    test_value = calcfunctions.AfterTaxIncome(*test_tuple)
    expected_value = 4000
    assert np.allclose(test_value, expected_value)


def test_ExpandIncome(skip_jit):
    '''
    Tests the ExpandIncome function
    '''
    test_tuple = (10000, 1000, 500, 100, 200, 300, 400, 20, 500, 50, 250, 10,
                  20, 30, 40, 60, 70, 80, 1500, 2000, 16380)
    test_value = calcfunctions.ExpandIncome(*test_tuple)
    expected_value = 16380
    assert np.allclose(test_value, expected_value)


tuple1 = (1, 1, 2, 0, 0, 1000)
tuple2 = (0, 1, 2, 0, 0, 1000)
tuple3 = (1, 1, 2, 100, 0, 1000)
tuple4 = (0, 2, 1, 100, 200, 1000)
tuple5 = (0, 1, 3, 100, 300, 1000)
expected1 = (0, 1000)
expected2 = (0, 1000)
expected3 = (0, 1000)
expected4 = (200, 1200)
expected5 = (300, 1300)


@pytest.mark.parametrize(
    'test_tuple,expected_value', [
        (tuple1, expected1), (tuple2, expected2), (tuple3, expected3),
        (tuple4, expected4), (tuple5, expected5)])
def test_LumpSumTax(test_tuple, expected_value, skip_jit):
    '''
    Tests LumpSumTax function
    '''
    test_value = calcfunctions.LumpSumTax(*test_tuple)
    assert np.allclose(test_value, expected_value)


FST_AGI_thd_lo_in = [1000000, 1000000, 500000, 1000000, 1000000]
FST_AGI_thd_hi_in = [2000000, 2000000, 1000000, 2000000, 2000000]
tuple1 = (1100000, 1, 1000, 100, 100, 0.1, FST_AGI_thd_lo_in,
          FST_AGI_thd_hi_in, 100, 200, 2000, 300)
tuple2 = (2100000, 1, 1000, 100, 100, 0.1, FST_AGI_thd_lo_in,
          FST_AGI_thd_hi_in, 100, 200, 2000, 300)
tuple3 = (1100000, 1, 1000, 100, 100, 0, FST_AGI_thd_lo_in,
          FST_AGI_thd_hi_in, 100, 200, 2000, 300)
tuple4 = (1100000, 2, 1000, 100, 100, 0.1, FST_AGI_thd_lo_in,
          FST_AGI_thd_hi_in, 100, 200, 2000, 300)
tuple5 = (2100000, 2, 1000, 100, 100, 0.1, FST_AGI_thd_lo_in,
          FST_AGI_thd_hi_in, 100, 200, 2000, 300)
tuple6 = (1100000, 2, 1000, 100, 100, 0, FST_AGI_thd_lo_in,
          FST_AGI_thd_hi_in, 100, 200, 2000, 300)
tuple7 = (510000, 3, 1000, 100, 100, 0.1, FST_AGI_thd_lo_in,
          FST_AGI_thd_hi_in, 100, 200, 2000, 300)
tuple8 = (1100000, 3, 1000, 100, 100, 0.1, FST_AGI_thd_lo_in,
          FST_AGI_thd_hi_in, 100, 200, 2000, 300)
tuple9 = (510000, 3, 1000, 100, 100, 0, FST_AGI_thd_lo_in,
          FST_AGI_thd_hi_in, 100, 200, 2000, 300)
expected1 = (10915, 11115, 12915, 11215)
expected2 = (209150, 209350, 211150, 209450)
expected3 = (0, 200, 2000, 300)
expected4 = (10915, 11115, 12915, 11215)
expected5 = (209150, 209350, 211150, 209450)
expected6 = (0, 200, 2000, 300)
expected7 = (1003, 1203, 3003, 1303)
expected8 = (109150, 109350, 111150, 109450)
expected9 = (0, 200, 2000, 300)


@pytest.mark.parametrize(
    'test_tuple,expected_value', [
        (tuple1, expected1), (tuple2, expected2), (tuple3, expected3),
        (tuple4, expected4), (tuple5, expected5), (tuple6, expected6),
        (tuple7, expected7), (tuple8, expected8), (tuple9, expected9)])
def test_FairShareTax(test_tuple, expected_value, skip_jit):
    '''
    Tests FairShareTax function
    '''
    test_value = calcfunctions.FairShareTax(*test_tuple)
    assert np.allclose(test_value, expected_value)


II_credit_ARPA = [0, 0, 0, 0, 0]
II_credit_ps_ARPA = [0, 0, 0, 0, 0]
II_credit_nr_ARPA = [0, 0, 0, 0, 0]
II_credit_nr_ps_ARPA = [0, 0, 0, 0, 0]
RRC_ps_ARPA = [75000, 150000, 75000, 112500, 150000]
RRC_pe_ARPA = [80000, 160000, 80000, 120000, 160000]
RRC_c_unit_ARPA = [0, 0, 0, 0, 0]
II_credit_CARES = [0, 0, 0, 0, 0]
II_credit_ps_CARES = [0, 0, 0, 0, 0]
II_credit_nr_CARES = [0, 0, 0, 0, 0]
II_credit_nr_ps_CARES = [0, 0, 0, 0, 0]
RRC_ps_CARES = [75000, 150000, 75000, 112500, 75000]
RRC_pe_CARES = [0, 0, 0, 0, 0]
RRC_c_unit_CARES = [1200, 2400, 1200, 1200, 1200]
tuple1 = (1, 50000, 1, 0, II_credit_ARPA, II_credit_ps_ARPA, 0,
          II_credit_nr_ARPA, II_credit_nr_ps_ARPA, 0, 1400, RRC_ps_ARPA,
          RRC_pe_ARPA, 0, 0, RRC_c_unit_ARPA, 0, 0, 0)
tuple2 = (1, 76000, 1, 0, II_credit_ARPA, II_credit_ps_ARPA, 0,
          II_credit_nr_ARPA, II_credit_nr_ps_ARPA, 0, 1400, RRC_ps_ARPA,
          RRC_pe_ARPA, 0, 0, RRC_c_unit_ARPA, 0, 0, 0)
tuple3 = (1, 90000, 1, 0, II_credit_ARPA, II_credit_ps_ARPA, 0,
          II_credit_nr_ARPA, II_credit_nr_ps_ARPA, 0, 1400, RRC_ps_ARPA,
          RRC_pe_ARPA, 0, 0, RRC_c_unit_ARPA, 0, 0, 0)
tuple4 = (2, 50000, 3, 1, II_credit_ARPA, II_credit_ps_ARPA, 0,
          II_credit_nr_ARPA, II_credit_nr_ps_ARPA, 0, 1400, RRC_ps_ARPA,
          RRC_pe_ARPA, 0, 0, RRC_c_unit_ARPA, 0, 0, 0)
tuple5 = (2, 155000, 4, 2, II_credit_ARPA, II_credit_ps_ARPA, 0,
          II_credit_nr_ARPA, II_credit_nr_ps_ARPA, 0, 1400, RRC_ps_ARPA,
          RRC_pe_ARPA, 0, 0, RRC_c_unit_ARPA, 0, 0, 0)
tuple6 = (2, 170000, 4, 2, II_credit_ARPA, II_credit_ps_ARPA, 0,
          II_credit_nr_ARPA, II_credit_nr_ps_ARPA, 0, 1400, RRC_ps_ARPA,
          RRC_pe_ARPA, 0, 0, RRC_c_unit_ARPA, 0, 0, 0)
tuple7 = (4, 50000, 2, 1, II_credit_ARPA, II_credit_ps_ARPA, 0,
          II_credit_nr_ARPA, II_credit_nr_ps_ARPA, 0, 1400, RRC_ps_ARPA,
          RRC_pe_ARPA, 0, 0, RRC_c_unit_ARPA, 0, 0, 0)
tuple8 = (4, 117000, 1, 0, II_credit_ARPA, II_credit_ps_ARPA, 0,
          II_credit_nr_ARPA, II_credit_nr_ps_ARPA, 0, 1400, RRC_ps_ARPA,
          RRC_pe_ARPA, 0, 0, RRC_c_unit_ARPA, 0, 0, 0)
tuple9 = (4, 130000, 1, 0, II_credit_ARPA, II_credit_ps_ARPA, 0,
          II_credit_nr_ARPA, II_credit_nr_ps_ARPA, 0, 1400, RRC_ps_ARPA,
          RRC_pe_ARPA, 0, 0, RRC_c_unit_ARPA, 0, 0, 0)
tuple10 = (1, 50000, 1, 0, II_credit_CARES, II_credit_ps_CARES, 0,
           II_credit_nr_CARES, II_credit_nr_ps_CARES, 0, 0, RRC_ps_CARES,
           RRC_pe_CARES, 0.05, 500, RRC_c_unit_CARES, 0, 0, 0)
tuple11 = (1, 97000, 2, 1, II_credit_CARES, II_credit_ps_CARES, 0,
           II_credit_nr_CARES, II_credit_nr_ps_CARES, 0, 0, RRC_ps_CARES,
           RRC_pe_CARES, 0.05, 500, RRC_c_unit_CARES, 0, 0, 0)
tuple12 = (1, 150000, 2, 1, II_credit_CARES, II_credit_ps_CARES, 0,
           II_credit_nr_CARES, II_credit_nr_ps_CARES, 0, 0, RRC_ps_CARES,
           RRC_pe_CARES, 0.05, 500, RRC_c_unit_CARES, 0, 0, 0)
tuple13 = (2, 50000, 4, 2, II_credit_CARES, II_credit_ps_CARES, 0,
           II_credit_nr_CARES, II_credit_nr_ps_CARES, 0, 0, RRC_ps_CARES,
           RRC_pe_CARES, 0.05, 500, RRC_c_unit_CARES, 0, 0, 0)
tuple14 = (2, 160000, 5, 3, II_credit_CARES, II_credit_ps_CARES, 0,
           II_credit_nr_CARES, II_credit_nr_ps_CARES, 0, 0, RRC_ps_CARES,
           RRC_pe_CARES, 0.05, 500, RRC_c_unit_CARES, 0, 0, 0)
tuple15 = (2, 300000, 2, 0, II_credit_CARES, II_credit_ps_CARES, 0,
           II_credit_nr_CARES, II_credit_nr_ps_CARES, 0, 0, RRC_ps_CARES,
           RRC_pe_CARES, 0.05, 500, RRC_c_unit_CARES, 0, 0, 0)
tuple16 = (4, 50000, 3, 2, II_credit_CARES, II_credit_ps_CARES, 0,
           II_credit_nr_CARES, II_credit_nr_ps_CARES, 0, 0, RRC_ps_CARES,
           RRC_pe_CARES, 0.05, 500, RRC_c_unit_CARES, 0, 0, 0)
tuple17 = (4, 130000, 2, 1, II_credit_CARES, II_credit_ps_CARES, 0,
           II_credit_nr_CARES, II_credit_nr_ps_CARES, 0, 0, RRC_ps_CARES,
           RRC_pe_CARES, 0.05, 500, RRC_c_unit_CARES, 0, 0, 0)
tuple18 = (4, 170000, 3, 2, II_credit_CARES, II_credit_ps_CARES, 0,
           II_credit_nr_CARES, II_credit_nr_ps_CARES, 0, 0, RRC_ps_CARES,
           RRC_pe_CARES, 0.05, 500, RRC_c_unit_CARES, 0, 0, 0)
expected1 = (0, 0, 1400)
expected2 = (0, 0, 1120)
expected3 = (0, 0, 0)
expected4 = (0, 0, 4200)
expected5 = (0, 0, 2800)
expected6 = (0, 0, 0)
expected7 = (0, 0, 2800)
expected8 = (0, 0, 560)
expected9 = (0, 0, 0)
expected10 = (0, 0, 1200)
expected11 = (0, 0, 600)
expected12 = (0, 0, 0)
expected13 = (0, 0, 3400)
expected14 = (0, 0, 3400)
expected15 = (0, 0, 0)
expected16 = (0, 0, 2200)
expected17 = (0, 0, 825)
expected18 = (0, 0, 0)


@pytest.mark.parametrize(
    'test_tuple,expected_value', [
        (tuple1, expected1), (tuple2, expected2), (tuple3, expected3),
        (tuple4, expected4), (tuple5, expected5), (tuple6, expected6),
        (tuple7, expected7), (tuple8, expected8), (tuple9, expected9),
        (tuple10, expected10), (tuple11, expected11), (tuple12, expected12),
        (tuple13, expected13), (tuple14, expected14), (tuple15, expected15),
        (tuple16, expected16), (tuple17, expected17), (tuple18, expected18)])
def test_PersonalTaxCredit(test_tuple, expected_value, skip_jit):
    """
    Tests the PersonalTaxCredit function
    """
    test_value = calcfunctions.PersonalTaxCredit(*test_tuple)
    assert np.allclose(test_value, expected_value)