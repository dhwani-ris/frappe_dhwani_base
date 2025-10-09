# dhwani_frappe_base/api/api_auth.py

import secrets

import frappe
from frappe import _
from frappe.auth import LoginManager
from frappe.rate_limiter import rate_limit

from .jwt_auth import encode_api_credentials

MOBILE_USER_ROLES = ["Mobile User"]
get_mobile_login_ratelimit = 5


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=get_mobile_login_ratelimit, seconds=60 * 60)
def login(username=None, password=None):
	"""Mobile app login handler"""
	try:
		# Use Frappe's login manager for authentication
		login_manager = LoginManager()
		login_manager.authenticate(username, password)
		login_manager.post_login()

		# Get user details using Frappe's session
		user = frappe.get_doc("User", frappe.session.user)

		# Check role using Frappe's permission system
		roles = frappe.get_roles()
		if not set(MOBILE_USER_ROLES).intersection(roles):
			raise frappe.PermissionError("User is not allowed to use mobile app")

		# Generate API keys if not exists
		if not user.api_key or not user.get_password("api_secret"):
			user.api_key = secrets.token_urlsafe(16)
			user.api_secret = secrets.token_urlsafe(32)
			user.save(ignore_permissions=True)
			frappe.db.commit()

		# Get API secret and generate token
		api_secret = user.get_password("api_secret")
		token = encode_api_credentials(user.api_key, api_secret)

		return {"message": _("Logged In"), "user": user.name, "full_name": user.full_name, "token": token}

	except frappe.AuthenticationError:
		frappe.throw(_("Invalid username or password or user is not allowed to use mobile app"))
	except frappe.PermissionError:
		frappe.throw(_("Not allowed to use mobile app"))
	except Exception as e:
		frappe.log_error(f"Mobile Login Error: {e}")
		frappe.throw(_("Unable to login"))


@frappe.whitelist(methods=["POST"])
def logout():
	"""Mobile app logout handler"""
	try:
		# Reset API credentials before logout
		user = frappe.get_doc("User", frappe.session.user)
		user.api_key = None
		user.api_secret = None
		user.save(ignore_permissions=True)
		frappe.db.commit()

		return {"message": _("Logged out successfully")}
	except Exception as e:
		frappe.log_error(f"Mobile Logout Error: {e}")
		frappe.throw(_("Unable to logout"))
