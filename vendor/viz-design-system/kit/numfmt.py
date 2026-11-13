"""Number formatting for the page kit (release 2.0.1). Mirrors kit/numfmt.js exactly.

Rules shared with the JavaScript twin and pinned by kit/numfmt-vectors.json:
- Negative values use U+2212 MINUS SIGN; signed=True adds an explicit plus.
  The sign follows the rounded value, so a value that rounds to zero has no sign.
- Rounding is half away from zero on the shortest decimal representation of the
  number (Python repr, JavaScript String), so both languages agree exactly.
- Any numbers.Real is accepted (numpy and pandas scalars included); an
  numbers.Integral is formatted from its exact integer value, so integers above
  2**53 print every digit, as the JavaScript twin does with BigInt. bool is rejected.
- currency (release 2.0.1 rule): >= 1B "$1.25B", >= 1M "$2.70M" (two decimals),
  10K to under 1M "$287K" (whole thousands), 1K to under 10K "$1.5K" (one decimal),
  else whole units. The tier is chosen again after rounding, so 9,950 is "$10K" (never
  "$10.0K"), 999,500 is "$1.00M" (never "$1000K") and 999.5 is "$1.0K".
  compact=False prints full units with thousands separators.
- percent: one decimal by default; ratio=True multiplies by 100 exactly.
- plural: "1 failed check", "2 failed checks".
Exact values belong in tables and downloads; these helpers are for display.
"""
from __future__ import annotations
import math
import numbers

MINUS = '−'
VERSION = '2.0.1'


def _decimal(value):
    """Return (sign, coefficient, exponent) with value = sign * coefficient * 10**exponent."""
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError('numfmt expects a finite number')
    if isinstance(value, numbers.Integral):
        text = str(int(value))
    else:
        value = float(value)
        if not math.isfinite(value):
            raise ValueError('numfmt expects a finite number')
        text = repr(value)
    sign = -1 if text.startswith('-') else 1
    text = text.lstrip('-')
    exponent = 0
    if 'e' in text:
        text, exp = text.split('e')
        exponent = int(exp)
    if '.' in text:
        whole, fraction = text.split('.')
        fraction = fraction.rstrip('0')
        exponent -= len(fraction)
        text = whole + fraction
    coefficient = int(text)
    if coefficient == 0:
        sign = 1
    return sign, coefficient, exponent


def _round(coefficient, exponent, decimals):
    """Round coefficient*10**exponent to `decimals` places; return integer units of 10**-decimals."""
    if exponent >= -decimals:
        return coefficient * 10 ** (exponent + decimals)
    divisor = 10 ** (-decimals - exponent)
    quotient, remainder = divmod(coefficient, divisor)
    return quotient + (1 if 2 * remainder >= divisor else 0)


def _at_least(coefficient, exponent, threshold):
    if exponent >= 0:
        return coefficient * 10 ** exponent >= threshold
    return coefficient >= threshold * 10 ** (-exponent)


def _group(digits):
    out = []
    while len(digits) > 3:
        out.insert(0, digits[-3:])
        digits = digits[:-3]
    out.insert(0, digits)
    return ','.join(out)


def _render(units, decimals):
    digits = str(units).rjust(decimals + 1, '0')
    whole = digits[:len(digits) - decimals] if decimals else digits
    text = _group(whole)
    if decimals:
        text += '.' + digits[-decimals:]
    return text


def _sign(sign, units, signed):
    if units == 0:
        return ''
    if sign < 0:
        return MINUS
    return '+' if signed else ''


def _check_decimals(decimals):
    if isinstance(decimals, bool) or not isinstance(decimals, int) or not 0 <= decimals <= 6:
        raise ValueError('decimals must be an integer from 0 to 6')


def number(value, decimals=0, signed=False):
    """Plain number with thousands separators: 2000 -> "2,000"; -6 -> "−6"."""
    _check_decimals(decimals)
    sign, coefficient, exponent = _decimal(value)
    units = _round(coefficient, exponent, decimals)
    return _sign(sign, units, signed) + _render(units, decimals)


def percent(value, decimals=1, signed=False, ratio=False):
    """Percentage, one decimal by default: 10.6 -> "10.6%"; ratio=True reads 0.106 as 10.6%."""
    _check_decimals(decimals)
    sign, coefficient, exponent = _decimal(value)
    if ratio:
        exponent += 2
    units = _round(coefficient, exponent, decimals)
    return _sign(sign, units, signed) + _render(units, decimals) + '%'


def currency(value, signed=False, compact=True, decimals=0, symbol='$'):
    """Currency: "$2.70M", "$287K", "$70"; compact=False prints "$2,700,000"."""
    _check_decimals(decimals)
    sign, coefficient, exponent = _decimal(value)
    if not compact:
        units = _round(coefficient, exponent, decimals)
        return _sign(sign, units, signed) + symbol + _render(units, decimals)
    # (smallest magnitude, divisor power, suffix, decimals, rounded units that promote to the next tier)
    order = [(0, 0, '', decimals, 1000 * 10 ** decimals), (3, 3, 'K', 1, 100), (4, 3, 'K', 0, 1000),
             (6, 6, 'M', 2, 1000 * 100), (9, 9, 'B', 2, None)]
    index = max(i for i, row in enumerate(order) if _at_least(coefficient, exponent, 10 ** row[0]) or i == 0)
    # The tier follows the rounded figure: promote when rounding reaches the next tier's floor.
    while True:
        _, power, suffix, places, promote = order[index]
        units = _round(coefficient, exponent - power, places)
        if promote is not None and units >= promote:
            index += 1
            continue
        return _sign(sign, units, signed) + symbol + _render(units, places) + suffix


def plural(count, singular, plural=None):
    """Count with a noun: plural(1, "failed check") -> "1 failed check"; 2 -> "2 failed checks"."""
    if isinstance(count, bool) or not isinstance(count, numbers.Real):
        raise ValueError('plural expects a whole-number count')
    if isinstance(count, numbers.Integral):
        count = int(count)
    else:
        count = float(count)
        if not count.is_integer():
            raise ValueError('plural expects a whole-number count')
        count = int(count)
    if count < 0:
        raise ValueError('plural expects a count of zero or more')
    word = singular if count == 1 else (plural if plural is not None else singular + 's')
    return number(count) + ' ' + word
