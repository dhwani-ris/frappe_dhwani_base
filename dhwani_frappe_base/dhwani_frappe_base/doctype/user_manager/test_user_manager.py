# Copyright (c) 2026, Dhwani RIS and Contributors
# See license.txt

from types import SimpleNamespace

import frappe
from frappe.tests import IntegrationTestCase
from frappe.tests import UnitTestCase
from dhwani_frappe_base.dhwani_frappe_base.doctype.user_manager.user_manager import UserManager

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


def _row(program, project):
	return SimpleNamespace(program=program, project=project)


class UnitTestUserManager(UnitTestCase):
	"""
	Unit tests for UserManager.
	Use this class for testing individual functions and methods.
	"""

	def setUp(self):
		self.user_manager = UserManager.__new__(UserManager)

	def test_allows_same_project_value_across_different_programs(self):
		"""Same record name under different Program (doctype) should not be flagged."""
		program_access_table = [
			_row("District", "Mandla"),
			_row("Block", "Mandla"),
		]
		# Should not raise
		self.user_manager._validate_program_access_duplicates(program_access_table)

	def test_blocks_exact_duplicate_program_and_project_pair(self):
		"""Same (program, project) pair repeated should be blocked."""
		program_access_table = [
			_row("District", "Mandla"),
			_row("District", "Mandla"),
		]
		with self.assertRaises(frappe.ValidationError):
			self.user_manager._validate_program_access_duplicates(program_access_table)

	def test_ignores_rows_without_project(self):
		"""Rows with no project value should be skipped, not counted as duplicates."""
		program_access_table = [
			_row("District", None),
			_row("Block", None),
		]
		# Should not raise
		self.user_manager._validate_program_access_duplicates(program_access_table)

	def test_allows_distinct_program_project_pairs(self):
		program_access_table = [
			_row("District", "Mandla"),
			_row("District", "Jabalpur"),
			_row("Block", "Mandla"),
		]
		# Should not raise
		self.user_manager._validate_program_access_duplicates(program_access_table)


class IntegrationTestUserManager(IntegrationTestCase):
	"""
	Integration tests for UserManager.
	Use this class for testing interactions between multiple components.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.role_profile_name = "Test UM Role Profile"
		if not frappe.db.exists("Role Profile", cls.role_profile_name):
			frappe.get_doc(
				{
					"doctype": "Role Profile",
					"role_profile": cls.role_profile_name,
					"roles": [{"role": "System Manager"}],
				}
			).insert(ignore_permissions=True)

		cls._ensure_state("Test UM Delhi", "TUD")
		cls._ensure_state("Test UM Maharashtra", "TUM")
		cls._ensure_district("Test UM Gurgaon", "TUG", "Test UM Delhi")

	@classmethod
	def _ensure_state(cls, state_name, state_code):
		if not frappe.db.exists("State", state_name):
			frappe.get_doc({"doctype": "State", "state_name": state_name, "state_code": state_code}).insert(
				ignore_permissions=True
			)

	@classmethod
	def _ensure_district(cls, district_name, district_code, state_name):
		if not frappe.db.exists("District", district_name):
			frappe.get_doc(
				{
					"doctype": "District",
					"district_name": district_name,
					"district_code": district_code,
					"state": state_name,
				}
			).insert(ignore_permissions=True)

	def _make_user_manager(self, email, program_access_rows):
		for doctype in ("User Manager", "User"):
			if frappe.db.exists(doctype, email):
				frappe.delete_doc(doctype, email, force=True, ignore_permissions=True)

		return frappe.get_doc(
			{
				"doctype": "User Manager",
				"email": email,
				"full_name": "Test Hierarchy User",
				"role_profiles": [{"role_profile": self.role_profile_name}],
				"table_fkmn": program_access_rows,
			}
		)

	def test_program_access_hierarchy_allows_consistent_values(self):
		"""District that actually belongs to the selected State should be allowed."""
		doc = self._make_user_manager(
			"test_hierarchy_consistent@example.com",
			[
				{"program": "State", "project": "Test UM Delhi"},
				{"program": "District", "project": "Test UM Gurgaon"},
			],
		)
		# Should not raise
		doc.insert(ignore_permissions=True)

	def test_program_access_hierarchy_blocks_inconsistent_values(self):
		"""District that belongs to a different State than the one selected should be rejected."""
		doc = self._make_user_manager(
			"test_hierarchy_inconsistent@example.com",
			[
				{"program": "State", "project": "Test UM Maharashtra"},
				{"program": "District", "project": "Test UM Gurgaon"},
			],
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_program_access_hierarchy_ignores_unrelated_doctypes(self):
		"""Doctypes with no Link relationship between them should not be cross-checked."""
		doc = self._make_user_manager(
			"test_hierarchy_unrelated@example.com",
			[
				{"program": "Role Profile", "project": self.role_profile_name},
				{"program": "District", "project": "Test UM Gurgaon"},
			],
		)
		# Should not raise: Role Profile has no Link field pointing at District (or vice versa)
		doc.insert(ignore_permissions=True)

	def test_program_access_is_not_mandatory(self):
		"""User Manager should save without any Program Access / User Permission rows."""
		email = "test_program_access_optional@example.com"
		for doctype in ("User Manager", "User"):
			if frappe.db.exists(doctype, email):
				frappe.delete_doc(doctype, email, force=True, ignore_permissions=True)

		doc = frappe.get_doc(
			{
				"doctype": "User Manager",
				"email": email,
				"full_name": "Test Program Access Optional",
				"role_profiles": [{"role_profile": self.role_profile_name}],
			}
		)
		# Should not raise, even with an empty Program Access table
		doc.insert(ignore_permissions=True)

		self.assertEqual(doc.get("table_fkmn"), [])

	def test_update_password_does_not_cause_timestamp_mismatch_on_next_save(self):
		"""Clearing new_password after a password change must not silently advance
		`modified` behind the client's back, or the very next save fails with
		TimestampMismatchError even though nothing else changed."""
		email = "test_password_timestamp@example.com"
		for doctype in ("User Manager", "User"):
			if frappe.db.exists(doctype, email):
				frappe.delete_doc(doctype, email, force=True, ignore_permissions=True)

		doc = frappe.get_doc(
			{
				"doctype": "User Manager",
				"email": email,
				"full_name": "Test Password Timestamp",
				"role_profiles": [{"role_profile": self.role_profile_name}],
			}
		)
		doc.insert(ignore_permissions=True)

		doc.new_password = "SomeStrongPassword123!"
		doc.save(ignore_permissions=True)

		db_modified = frappe.db.get_value("User Manager", doc.name, "modified")
		self.assertEqual(
			str(db_modified),
			str(doc.modified),
			"new_password cleanup must not advance `modified` beyond what the client received",
		)

		# Should not raise TimestampMismatchError: the client's in-memory `modified`
		# must still match the DB after the password-change save.
		doc.full_name = "Test Password Timestamp Updated"
		doc.save(ignore_permissions=True)
