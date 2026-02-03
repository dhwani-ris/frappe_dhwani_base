# Copyright (c) 2026, Dhwani RIS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists
from frappe.utils.password import update_password
from dhwani_frappe_base.utils.aadhaar_validation import validate_aadhaar_number

SYNC_FLAG_USER_TO_DHWANI = "syncing_user_to_dhwani"


class UserManager(Document):
	def _get_table_field_name(self, child_doctype):
		"""Get the field name in this doctype that contains the specified child table"""
		try:
			meta = frappe.get_meta(self.doctype)
			for field in meta.fields:
				if field.fieldtype == "Table" and field.options == child_doctype:
					return field.fieldname
		except Exception:
			pass
		return None

	def _get_program_access_table(self):
		"""Get the Program Access child table"""
		table_field = self._get_table_field_name("Program Access")
		if table_field and hasattr(self, table_field):
			return getattr(self, table_field)
		return None

	def _get_role_profiles_table(self):
		"""Get the Role Profiles child table"""
		if frappe.db.exists("DocType", "User Role Profile"):
			table_field = self._get_table_field_name("User Role Profile")
			if table_field and hasattr(self, table_field):
				return getattr(self, table_field)

		# Fallback: try common field names
		for field_name in ["role_profiles", "user_role_profiles"]:
			if hasattr(self, field_name):
				return getattr(self, field_name)
		return None

	def validate(self):
		"""Core validation only"""
		if not self.email:
			frappe.throw(_("Email is required"))

		role_profiles_table = self._get_role_profiles_table()
		has_role_profile = False
		if role_profiles_table:
			for role_row in role_profiles_table:
				role_profile_value = getattr(role_row, "role_profile", None) or getattr(
					role_row, "user_role_profile", None
				)
				if role_profile_value:
					has_role_profile = True
					break

		if not has_role_profile:
			frappe.throw(_("Please select at least one Role Profile"))

		program_access_table = self._get_program_access_table()
		if not program_access_table or len(program_access_table) == 0:
			frappe.throw(_("Please add at least one Program Access"))

		# Validate for duplicate projects and programs
		self._validate_program_access_duplicates(program_access_table)

		if self.aadhaar_number:
			validate_aadhaar_number(self.aadhaar_number)

		new_password = self.get("new_password")
		if new_password:
			if not self.is_dummy_password(new_password):
				self.flags.new_password_value = new_password

	def on_trash(self):
		"""Delete related records when User Manager is deleted"""
		if not self.email:
			return

		self.delete_user_permissions_for_email()
		self.delete_user_record()

	def on_update(self):
		"""Create/Update User Permission records and User doctype"""
		if not self.email:
			return

		if hasattr(self.flags, "new_password_value") and self.flags.new_password_value:
			self.update_user_password()

		user = self.get_user_from_email()
		if not user:
			return

		self.delete_existing_user_permissions(user)

		program_access_table = self._get_program_access_table()
		if program_access_table:
			for row in program_access_table:
				program_value = getattr(row, "program", None)
				project_value = getattr(row, "project", None)
				if program_value and project_value:
					# Dynamic Link: allow = program_value (doctype), for_value = project_value
					self.create_user_permission(user, program_value, project_value)

		self.sync_to_user_doctype(user)

	def get_user_from_email(self):
		"""Get user from email, create if doesn't exist"""
		if not self.email:
			return None

		if frappe.db.exists("User", self.email):
			return self.email

		setattr(frappe.flags, SYNC_FLAG_USER_TO_DHWANI, True)
		try:
			user_doc = self._create_user_document()
			self._apply_role_profiles_to_user(user_doc)
			self._apply_roles_to_user(user_doc)
			user_doc.flags.ignore_validate = True
			user_doc.save(ignore_permissions=True)
			self._sync_username_from_user()
			return self.email
		except Exception as e:
			frappe.throw(_("Error creating user: {0}").format(e))
		finally:
			try:
				if hasattr(frappe.flags, SYNC_FLAG_USER_TO_DHWANI):
					delattr(frappe.flags, SYNC_FLAG_USER_TO_DHWANI)
			except (KeyError, AttributeError):
				pass

	def _create_user_document(self):
		"""Create new User document"""
		user_doc = frappe.get_doc(
			{
				"doctype": "User",
				"email": self.email,
				"first_name": self.full_name or self.email.split("@")[0],
				"full_name": self.full_name or self.email.split("@")[0],
				"enabled": 1,
				"send_welcome_email": 1,
			}
		)

		# Generate username before insert (matching Frappe's logic)
		if not user_doc.username and user_doc.first_name:
			base_username = frappe.scrub(user_doc.first_name)
			if base_username:
				user_doc.username = append_number_if_name_exists("User", base_username, fieldname="username")

		user_doc.flags.ignore_validate = True
		user_doc.insert(ignore_permissions=True)
		user_doc.reload()

		return user_doc

	def _apply_role_profiles_to_user(self, user_doc):
		"""Apply role profiles from User Manager to User"""
		role_profiles_table = self._get_role_profiles_table()
		if role_profiles_table and hasattr(user_doc, "role_profiles"):
			user_doc.role_profiles = []
			for role_row in role_profiles_table:
				role_profile_value = getattr(role_row, "role_profile", None) or getattr(
					role_row, "user_role_profile", None
				)
				if role_profile_value:
					user_doc.append("role_profiles", {"role_profile": role_profile_value})

	def _apply_roles_to_user(self, user_doc):
		"""Apply roles from User Manager to User"""
		roles_list = self._get_all_roles()
		if roles_list:
			user_doc.add_roles(*roles_list)

	def _sync_username_from_user(self):
		"""Sync username from User to User Manager"""
		username = frappe.db.get_value("User", self.email, "username")
		if username:
			self.db_set("username", username, update_modified=False)

	def delete_existing_user_permissions(self, user):
		"""Delete all existing User Permission records for the given user"""
		if not user:
			return
		try:
			# Bulk delete all user permissions for this user
			frappe.db.delete("User Permission", {"user": user})
		except Exception as e:
			frappe.log_error(f"Error deleting user permissions: {str(e)}")

	def create_user_permission(self, user, allow, for_value):
		"""Create a User Permission record"""
		if not user or not allow or not for_value:
			return

		try:
			# Check if already exists (query directly to avoid race conditions)
			existing = frappe.db.exists(
				"User Permission", {"user": user, "allow": allow, "for_value": for_value}
			)

			if existing:
				return

			user_permission = frappe.get_doc(
				{
					"doctype": "User Permission",
					"user": user,
					"allow": allow,
					"for_value": for_value,
					"apply_to_all_doctypes": 1,
				}
			)
			user_permission.insert(ignore_permissions=True, ignore_links=True)
		except Exception as e:
			frappe.throw(_("Error creating User Permission: {0}").format(e))

	def _get_roles_from_role_profile(self, role_profile_value):
		"""Get all Role names directly from Role Profile value"""
		if not role_profile_value:
			return []

		roles = []
		try:
			if frappe.db.exists("Role Profile", role_profile_value):
				role_profile_doc = frappe.get_doc("Role Profile", role_profile_value)
				if role_profile_doc.roles:
					for role_row in role_profile_doc.roles:
						if role_row.role:
							roles.append(role_row.role)
			elif frappe.db.exists("Role", role_profile_value):
				roles.append(role_profile_value)
		except Exception as e:
			frappe.throw(_("Error getting roles from Role Profile {0}: {1}").format(role_profile_value, e))

		return roles

	def sync_to_user_doctype(self, user_email):
		"""Sync all fields automatically to User doctype"""
		if not user_email or not frappe.db.exists("User", user_email):
			return
		# Check if sync is already in progress to prevent loops
		if getattr(frappe.flags, SYNC_FLAG_USER_TO_DHWANI, False):
			return
		# Use a flag to prevent concurrent syncs
		sync_flag = f"syncing_user_{user_email}"
		if hasattr(frappe.flags, sync_flag) and getattr(frappe.flags, sync_flag, False):
			return
		try:
			setattr(frappe.flags, sync_flag, True)
			user_doc = frappe.get_doc("User", user_email)
			user_doc.reload()
			has_changes = False
			dhwani_meta = frappe.get_meta("User Manager")
			has_changes = self._sync_common_fields(user_doc, dhwani_meta) or has_changes
			has_changes = self._sync_role_profiles(user_doc) or has_changes
			has_changes = self._sync_roles(user_doc) or has_changes
			if has_changes:
				user_doc.reload()
				self._sync_common_fields(user_doc, dhwani_meta)
				self._sync_role_profiles(user_doc)
				self._sync_roles(user_doc)
				# Set flag to prevent User->Dhwani sync loop
				setattr(frappe.flags, SYNC_FLAG_USER_TO_DHWANI, True)
				try:
					user_doc.flags.ignore_validate = True
					user_doc.save(ignore_permissions=True)
				finally:
					if hasattr(frappe.flags, SYNC_FLAG_USER_TO_DHWANI):
						delattr(frappe.flags, SYNC_FLAG_USER_TO_DHWANI)
		except Exception as e:
			error_msg = str(e)
			if "has been modified" in error_msg:
				# Version conflict - will sync on next save, not critical
				pass
			else:
				frappe.throw(_("Error syncing to User doctype: {0}").format(e))
		finally:
			try:
				if hasattr(frappe.flags, sync_flag):
					delattr(frappe.flags, sync_flag)
			except (KeyError, AttributeError):
				pass

	def _sync_common_fields(self, user_doc, dhwani_meta):
		"""Sync common fields from User Manager to User doctype"""
		has_changes = False
		for field in dhwani_meta.fields:
			if field.fieldtype in [
				"Data",
				"Small Text",
				"Text",
				"Int",
				"Float",
				"Date",
				"Datetime",
				"Link",
				"Select",
				"Phone",
				"Check",
				"Attach Image",
				"Image",
			]:
				fieldname = field.fieldname
				if fieldname in [
					"name",
					"owner",
					"creation",
					"modified",
					"modified_by",
					"idx",
					"cover_image",
				]:
					continue

				if hasattr(self, fieldname) and hasattr(user_doc, fieldname):
					dhwani_value = getattr(self, fieldname, None)
					user_value = getattr(user_doc, fieldname, None)

					# Normalize None and empty string values for comparison
					dhwani_normalized = dhwani_value if dhwani_value not in [None, ""] else None
					user_normalized = user_value if user_value not in [None, ""] else None

					if dhwani_normalized != user_normalized:
						setattr(user_doc, fieldname, dhwani_value)
						has_changes = True
		return has_changes

	def _sync_role_profiles(self, user_doc):
		"""Sync role profiles from User Manager to User doctype"""
		has_changes = False
		if hasattr(user_doc, "role_profiles"):
			current_role_profiles = [
				getattr(r, "role_profile", None)
				for r in user_doc.role_profiles
				if getattr(r, "role_profile", None)
			]
			dhwani_role_profiles = []
			role_profiles_table = self._get_role_profiles_table()
			if role_profiles_table:
				for role_row in role_profiles_table:
					role_profile_value = getattr(role_row, "role_profile", None) or getattr(
						role_row, "user_role_profile", None
					)
					if role_profile_value:
						dhwani_role_profiles.append(role_profile_value)

			if set(current_role_profiles) != set(dhwani_role_profiles):
				user_doc.role_profiles = []
				for role_profile_value in dhwani_role_profiles:
					user_doc.append("role_profiles", {"role_profile": role_profile_value})
				has_changes = True
		return has_changes

	def _sync_roles(self, user_doc):
		"""Sync roles from User Manager to User doctype"""
		has_changes = False
		roles_list = self._get_all_roles()
		if roles_list:
			current_roles = [r.role for r in user_doc.roles if r.role]
			roles_to_add = [r for r in roles_list if r not in current_roles]
			if roles_to_add:
				user_doc.add_roles(*roles_to_add)
				has_changes = True
		return has_changes

	def update_user_password(self):
		"""Update User password when new_password is set"""
		password_value = getattr(self.flags, "new_password_value", None)

		if not password_value:
			new_password = self.get("new_password")
			if new_password and not self.is_dummy_password(new_password):
				password_value = new_password

		if not self.email or not password_value:
			return

		try:
			if not frappe.db.exists("User", self.email):
				frappe.throw(_("User {0} does not exist").format(self.email))

			update_password(
				self.email, password_value, doctype="User", fieldname="password", logout_all_sessions=False
			)

			frappe.db.set_value("User Manager", self.name, "new_password", None)

			frappe.msgprint(
				_("Password updated successfully for user {0}").format(self.email),
				indicator="green",
				alert=True,
			)
		except Exception as e:
			frappe.throw(_("Failed to update password: {0}").format(str(e)))

	def delete_user_permissions_for_email(self):
		"""Delete all User Permission records for this email"""
		if not self.email:
			return

		try:
			self.delete_existing_user_permissions(self.email)
		except Exception as e:
			frappe.throw(_("Error deleting User Permissions: {0}").format(e))

	def delete_user_record(self):
		"""Delete User record"""
		if not self.email:
			return

		try:
			if frappe.db.exists("User", self.email) and self.email not in ["Administrator", "Guest"]:
				frappe.delete_doc("User", self.email, ignore_permissions=True, force=True)
		except Exception as e:
			frappe.throw(_("Error deleting User record: {0}").format(e))

	def _validate_program_access_duplicates(self, program_access_table):
		"""Validate that there are no duplicate projects or programs in Program Access table"""
		projects = [row.project for row in program_access_table if row.project]
		if len(projects) != len(set(projects)):
			frappe.throw(_("Project must be unique"))

	def _get_all_roles(self):
		"""Get all roles from role_profiles"""
		roles = []
		role_profiles_table = self._get_role_profiles_table()
		if not role_profiles_table:
			return roles

		for role_row in role_profiles_table:
			role_profile_value = getattr(role_row, "role_profile", None) or getattr(
				role_row, "user_role_profile", None
			)
			if role_profile_value:
				roles.extend(self._get_roles_from_role_profile(role_profile_value))

		return list(set(roles))


def sync_user_to_user_manager(doc, method):
	"""Sync User doctype changes to User Manager"""
	if not doc.email:
		return

	# Check if sync is already in progress to prevent loops
	if getattr(frappe.flags, SYNC_FLAG_USER_TO_DHWANI, False):
		return

	if not frappe.db.exists("DocType", "User Role Profile"):
		return

	try:
		setattr(frappe.flags, SYNC_FLAG_USER_TO_DHWANI, True)
		dhwani_doc, is_new = _get_or_create_dhwani_doc(doc)
		has_changes = is_new or _sync_fields_from_user(doc, dhwani_doc)

		if has_changes:
			dhwani_doc.flags.ignore_validate = True
			dhwani_doc.save(ignore_permissions=True)
	except Exception as e:
		if "User Role Profile" in str(e) or "No module named" in str(e):
			return
		frappe.throw(_("Error syncing User to User Manager: {0}").format(e))
	finally:
		try:
			if hasattr(frappe.flags, SYNC_FLAG_USER_TO_DHWANI):
				delattr(frappe.flags, SYNC_FLAG_USER_TO_DHWANI)
		except (KeyError, AttributeError):
			pass


def _get_or_create_dhwani_doc(user_doc):
	"""Get or create User Manager document"""
	dhwani_user = frappe.db.get_value("User Manager", {"email": user_doc.email}, "name")

	if dhwani_user:
		return frappe.get_doc("User Manager", dhwani_user), False

	return frappe.get_doc(
		{
			"doctype": "User Manager",
			"email": user_doc.email,
			"full_name": user_doc.full_name or user_doc.first_name or user_doc.email.split("@")[0],
			"mobile_no": getattr(user_doc, "mobile_no", None) or "",
			"username": getattr(user_doc, "username", None) or "",
		}
	), True


def _sync_fields_from_user(user_doc, dhwani_doc):
	"""Sync all fields automatically from User to Dhwani - same field names"""
	has_changes = False

	user_meta = frappe.get_meta("User")
	dhwani_meta = frappe.get_meta("User Manager")

	user_fieldnames = {f.fieldname for f in user_meta.fields}
	dhwani_fieldnames = {f.fieldname for f in dhwani_meta.fields}

	common_fields = user_fieldnames & dhwani_fieldnames

	for fieldname in common_fields:
		if fieldname in ["name", "owner", "creation", "modified", "modified_by", "idx"]:
			continue

		if hasattr(user_doc, fieldname) and hasattr(dhwani_doc, fieldname):
			user_value = getattr(user_doc, fieldname, None)
			dhwani_value = getattr(dhwani_doc, fieldname, None)

			if user_value != dhwani_value:
				if fieldname == "username":
					setattr(dhwani_doc, fieldname, user_value or "")
				elif user_value:
					setattr(dhwani_doc, fieldname, user_value)
				has_changes = True

	return has_changes


@frappe.whitelist()
def get_username_from_user(email):
	"""Get username from User doctype for given email"""
	if not email:
		return {"username": ""}

	if frappe.db.exists("User", email):
		username = frappe.db.get_value("User", email, "username")
		return {"username": username or ""}

	return {"username": ""}
