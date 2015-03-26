import numpy as np
from numpy import min, max, float, array, float64
#from PyscesToolBox import PyscesToolBox as PYCtools
from sympy import Symbol
#from IPython.display import Latex
from ...utils.misc import silence_print, DotDict, formatter_factory
from ...utils.plotting import Data2D
from ... import modeltools
from pysces import ModelMap


def cctype(obj):
    return 'ccobjects' in str(type(obj))


@silence_print
def get_state(mod, do_state=False):
    if do_state:
        mod.doState()
    ss = [getattr(mod, 'J_' + r) for r in mod.reactions] + \
        [getattr(mod, s + '_ss') for s in mod.species]
    return ss


@silence_print
def silent_mca(mod):
    mod.doMca()


def get_value_eval(expression, subs_dict):
    for k, v in subs_dict.iteritems():
        subs_dict[k] = float64(v)
    ans = eval(expression, {}, subs_dict)
    return ans


class StateKeeper:

    def __init__(self, state):
        self._last_state_for_mca = state

    def do_mca_state(self, mod, state):
        if state != self._last_state_for_mca:
            silent_mca(mod)
            self._last_state_for_mca = state


class CCBase(object):

    """The base object for the control coefficients and control patterns"""

    def __init__(self, mod, name, expression, ltxe):
        super(CCBase, self).__init__()

        self.expression = expression
        self.mod = mod
        self._ltxe = ltxe
        self.name = name
        self._latex_name = '\\Sigma'

        self._str_expression_ = None
        self._value = None
        self._latex_expression = None

    @property
    def latex_expression(self):
        if not self._latex_expression:
            self._latex_expression = self._ltxe.expression_to_latex(
                self.expression
            )
        return self._latex_expression

    @property
    def latex_name(self):
        return self._latex_name

    @property
    def _str_expression(self):
        if not self._str_expression_:
            self._str_expression_ = str(self.expression)
        return self._str_expression_

    @property
    def value(self):
        """The value property. Calls self._calc_value() when self._value
        is None and returns self._value"""
        self._calc_value()
        return self._value

    def _repr_latex_(self):
        return '$%s = %s = %.3f$' % (self.latex_name,
                                     self.latex_expression,
                                     self.value)

    def _calc_value(self):
        """Calculates the value of the expression"""
        keys = self.expression.atoms(Symbol)
        subsdict = {}
        for key in keys:
            str_key = str(key)
            subsdict[str_key] = getattr(self.mod, str_key)
        self._value = get_value_eval(self._str_expression, subsdict)

    def __repr__(self):
        return self.expression.__repr__()

    def __add__(self, other):
        if cctype(other):
            return self.expression.__add__(other.expression)
        else:
            return self.expression.__add__(other)

    def __mul__(self, other):
        if cctype(other):
            return self.expression.__mul__(other.expression)
        else:
            return self.expression.__mul__(other)

    def __div__(self, other):
        if cctype(other):
            return self.expression.__div__(other.expression)
        else:
            return self.expression.__div__(other)

    def __pow__(self, other):
        if cctype(other):
            return self.expression.__pow__(other.expression)
        else:
            return self.expression.__pow__(other)


class CCoef(CCBase):

    """The object the stores control coefficients. Inherits from CCBase"""

    def __init__(self, mod, name, expression, denominator, ltxe):
        super(CCoef, self).__init__(mod, name, expression, ltxe)
        self.numerator = expression
        self.denominator = denominator.expression
        self.expression = self.numerator / denominator.expression
        self.denominator_object = denominator

        self._latex_numerator = None
        self._latex_expression_full = None
        self._latex_expression = None
        self._latex_name = None

        self.control_patterns = None

        self._set_control_patterns()

    @property
    def latex_numerator(self):
        if not self._latex_numerator:
            self._latex_numerator = self._ltxe.expression_to_latex(
                self.numerator
            )
        return self._latex_numerator

    @property
    def latex_expression_full(self):
        if not self._latex_expression_full:
            full_expr = '\\frac{' + self.latex_numerator + '}{' \
                + self.denominator_object.latex_expression + '}'
            self._latex_expression_full = full_expr
        return self._latex_expression_full

    @property
    def latex_expression(self):
        if not self._latex_expression:
            self._latex_expression = '(' + \
                self.latex_numerator + ')' + '/ \\,\\Sigma'
        return self._latex_expression

    @property
    def latex_name(self):
        if not self._latex_name:
            self._latex_name = self._ltxe.expression_to_latex(
                self.name
            )
        return self._latex_name

    def _perscan(self, parameter, scan_range):

        scan_res = [list() for i in range(len(self.control_patterns.values()) + 1)]
        scan_res[0] = scan_range

        for parvalue in scan_range:
            setattr(self.mod, parameter, parvalue)
            self.mod.SetQuiet()
            self.mod.doMca()
            self.mod.SetLoud()
            for i, cp in enumerate(self.control_patterns.values()):
                    scan_res[i + 1].append(cp.percentage)

        return scan_res


    def _valscan(self, parameter, scan_range):

        scan_res = [list() for i in range(len(self.control_patterns.values()) + 2)]
        scan_res[0] = scan_range

        for parvalue in scan_range:
            setattr(self.mod, parameter, parvalue)
            self.mod.SetQuiet()
            self.mod.doMca()
            self.mod.SetLoud()

            for i, cp in enumerate(self.control_patterns.values()):
                scan_res[i + 1].append(cp.value)

            scan_res[i + 2].append(self.value)

        return scan_res

    def par_scan(self, parameter, scan_range, scan_type='percentage', init_return=True):

        assert scan_type in ['percentage', 'value']
        init = getattr(self.mod, parameter)

        if scan_type is 'percentage':
            column_names = [parameter] + \
                [cp.name for cp in self.control_patterns.values()]
            y_label = 'Control pattern percentage contribution'
            scan_res = self._perscan(parameter,scan_range)
        elif scan_type is 'value':
            column_names = [
                parameter] + [cp.name for cp in self.control_patterns.values()] + [self.name]
            y_label = 'Control coefficient/pattern value'
            scan_res = self._valscan(parameter,scan_range)

        if init_return:
            self.mod.SetQuiet()
            setattr(self.mod, parameter, init)
            self.mod.doMca()
            self.mod.SetLoud()

        mm = ModelMap(self.mod)
        species = mm.hasSpecies()
        if parameter in species:
            x_label = '[%s]' % parameter.replace('_', ' ')
        else:
            x_label = parameter
        ax_properties = {'ylabel': y_label,
                         'xlabel': x_label,
                         'xscale': 'linear',
                         'yscale': 'linear',
                         'xlim': [scan_range[0], scan_range[-1]]}
        data_array = array(scan_res, dtype=np.float).transpose()
        data = Data2D(
            self.mod, column_names, data_array, self._ltxe, 'symca', ax_properties)

        return data


    def _recalculate_value(self):
        """Recalculates the control coefficients and control pattern
           values. calls _calc_value() for self and each control
           pattern. Useful for when model parameters change"""
        self._calc_value()

    def _calc_value(self):
        """Calculates the numeric value of the control pattern from the
           values of its control patterns."""
        keys = self.expression.atoms(Symbol)
        subsdict = {}
        for key in keys:
            str_key = str(key)
            subsdict[str_key] = getattr(self.mod, str_key)
        for pattern in self.control_patterns.values():
            pattern._calc_value(subsdict)
        self._value = sum(
            [pattern._value for pattern in self.control_patterns.values()])

    def _set_control_patterns(self):
        """Divides control coefficient into control patterns and saves
           results in self.CPx where x is a number is the number of the
           control pattern as it appears in in control coefficient
           expression"""
        patterns = self.numerator.as_coeff_add()[1]
        cps = DotDict()
        cps._make_repr('v.name', 'v.value', formatter_factory())
        for i, pattern in enumerate(patterns):
            name = 'CP' + str(1 + i)
            cp = CPattern(self.mod,
                          name,
                          pattern,
                          self.denominator_object,
                          self,
                          self._ltxe)
            setattr(self, name, cp)
            cps[name] = cp
        self.control_patterns = cps
        #assert self._check_control_patterns == True

    def _check_control_patterns(self):
        """Checks that all control patterns are either positive or negative"""
        all_same = False
        poscomp = [i.value > 0 for i in self.control_patterns.values()]
        negcomp = [i.value < 0 for i in self.control_patterns.values()]
        if all(poscomp):
            all_same = True
        elif all(negcomp):
            all_same = True
        return all_same


class CPattern(CCBase):

    """docstring for CPattern"""

    def __init__(self,
                 mod,
                 name,
                 expression,
                 denominator,
                 parent,
                 ltxe):
        super(CPattern, self).__init__(mod,
                                       name,
                                       expression,
                                       ltxe)
        self.numerator = expression
        self.denominator = denominator.expression
        self.expression = self.numerator / denominator.expression
        self.denominator_object = denominator
        self.parent = parent

        self._latex_numerator = None
        self._latex_expression_full = None
        self._latex_expression = None
        self._latex_name = None
        self._percentage = None

    def _calc_value(self, subsdict=None):
        """Calculates the value of the expression"""
        if subsdict is None:
            keys = self.expression.atoms(Symbol)
            subsdict = {}
            for key in keys:
                str_key = str(key)
                subsdict[str_key] = getattr(self.mod, str_key)
        self._value = get_value_eval(self._str_expression, subsdict)

    @property
    def latex_numerator(self):
        if not self._latex_numerator:
            self._latex_numerator = self._ltxe.expression_to_latex(
                self.numerator
            )
        return self._latex_numerator

    @property
    def latex_expression_full(self):
        if not self._latex_expression_full:
            full_expr = '\\frac{' + self.latex_numerator + '}{' \
                + self.denominator_object.latex_expression + '}'
            self._latex_expression_full = full_expr
        return self._latex_expression_full

    @property
    def latex_expression(self):
        if not self._latex_expression:
            self._latex_expression = self.latex_numerator + '/ \\,\\Sigma'
        return self._latex_expression

    @property
    def latex_name(self):
        if not self._latex_name:
            self._latex_name = self.name
        return self._latex_name

    @property
    def percentage(self):
        self._percentage = (self.value / self.parent.value) * 100
        return self._percentage
