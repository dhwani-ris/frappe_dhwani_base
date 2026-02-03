# Copyright (c) 2026, Dhwani RIS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

"""
Aadhaar Number Validation Utility

This module provides validation functions for Aadhaar numbers using the Verhoeff algorithm.
Aadhaar numbers are 12-digit unique identification numbers issued by UIDAI (India).

Usage:
    # With error throwing (default)
    validate_aadhaar_number("1234 5678 9012")

    # Without error throwing (returns boolean)
    is_valid = validate_aadhaar_number("1234 5678 9012", throw_error=False)
"""

# Verhoeff algorithm lookup tables for Aadhaar validation
_VERHOEFF_D_TABLE = [
	[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
	[1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
	[2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
	[3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
	[4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
	[5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
	[6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
	[7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
	[8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
	[9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

_VERHOEFF_P_TABLE = [
	[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
	[1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
	[5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
	[8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
	[9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
	[4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
	[2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
	[7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def validate_aadhaar_number(aadhaar_number, throw_error=True):
	"""
	Validate Aadhaar number using Verhoeff algorithm.

	Args:
		aadhaar_number: Aadhaar number string (can contain spaces or hyphens)
		throw_error: If True, throws frappe.throw with error message. If False, returns boolean.

	Returns:
		If throw_error=False: True if valid, False otherwise
		If throw_error=True: None (throws error if invalid)

	Example:
		validate_aadhaar_number("1234 5678 9012")  # Throws error if invalid
		validate_aadhaar_number("1234 5678 9012", throw_error=False)  # Returns True/False
	"""
	if not aadhaar_number:
		if throw_error:
			frappe.throw(_("Aadhaar number is required"))
		return False

	# Clean the Aadhaar number (remove spaces and hyphens)
	aadhaar_clean = _clean_aadhaar_number(aadhaar_number)

	# Validate basic format with specific error messages
	format_error = _validate_aadhaar_format(aadhaar_clean)
	if format_error is not True:
		if throw_error:
			frappe.throw(_(format_error))
		return False

	# Validate using Verhoeff algorithm
	is_valid = _validate_aadhaar_verhoeff(aadhaar_clean)

	if not is_valid and throw_error:
		frappe.throw(_("Invalid Aadhaar number"))

	return is_valid


def _clean_aadhaar_number(aadhaar_number):
	"""
	Clean Aadhaar number by removing spaces and hyphens.

	Args:
		aadhaar_number: Aadhaar number string

	Returns:
		Cleaned Aadhaar number string
	"""
	return aadhaar_number.replace(" ", "").replace("-", "").strip()


def _validate_aadhaar_format(aadhaar):
	"""
	Validate basic Aadhaar number format.

	Args:
		aadhaar: Clean Aadhaar number string

	Returns:
		True if format is valid, error message string otherwise
	"""
	if not aadhaar:
		return "Aadhaar number is required"
	
	if not aadhaar.isdigit():
		return "Aadhaar number must contain only digits"
	
	if len(aadhaar) != 12:
		return "Aadhaar number must be exactly 12 digits"

	# Check for invalid patterns (all same digits like 111111111111)
	if len(set(aadhaar)) == 1:
		return "Aadhaar number cannot have all same digits"

	# Check for sequential patterns (123456789012, 012345678901)
	if _is_sequential_pattern(aadhaar):
		return "Aadhaar number cannot be a sequential pattern"

	return True


def _is_sequential_pattern(aadhaar):
	"""
	Check if Aadhaar number follows sequential pattern.

	Args:
		aadhaar: Aadhaar number string

	Returns:
		True if sequential pattern detected, False otherwise
	"""
	# Check for ascending sequence
	is_ascending = all(int(aadhaar[i]) == (int(aadhaar[i - 1]) + 1) % 10 for i in range(1, len(aadhaar)))

	# Check for descending sequence
	is_descending = all(int(aadhaar[i]) == (int(aadhaar[i - 1]) - 1) % 10 for i in range(1, len(aadhaar)))

	return is_ascending or is_descending


def _validate_aadhaar_verhoeff(aadhaar):
	"""
	Validate Aadhaar using Verhoeff algorithm.

	Args:
		aadhaar: Clean Aadhaar number string (12 digits, no spaces/hyphens)

	Returns:
		True if valid, False otherwise
	"""
	c = 0
	reversed_digits = [int(digit) for digit in reversed(aadhaar)]
	for i in range(len(reversed_digits)):
		c = _VERHOEFF_D_TABLE[c][_VERHOEFF_P_TABLE[i % 8][reversed_digits[i]]]

	return c == 0
