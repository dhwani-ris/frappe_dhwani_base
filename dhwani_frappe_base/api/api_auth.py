# dhwani_frappe_base/api/api_auth.py

import secrets
from typing import Any

import frappe
from frappe import _
from frappe.auth import LoginManager, get_login_attempt_tracker
from frappe.rate_limiter import rate_limit
from frappe.utils import validate_phone_number
from frappe.utils.mobile_otp import find_user_by_mobile, is_mobile_otp_login_enabled, send_mobile_login_otp

from .jwt_auth import encode_api_credentials

MOBILE_USER_ROLES = ["Mobile User"]
get_mobile_login_ratelimit = 5
get_mobile_otp_ratelimit = 5


def _authenticate_user(username: str | None, password: str | None) -> Any:
	"""Authenticate user using Frappe's login manager"""
	login_manager = LoginManager()
	login_manager.authenticate(username, password)
	login_manager.post_login()
	return frappe.get_doc("User", frappe.session.user)


def _validate_mobile_user_role() -> None:
	"""Validate if user has mobile user role"""
	roles = frappe.get_roles()
	if not set(MOBILE_USER_ROLES).intersection(roles):
		raise frappe.PermissionError(_("User is not allowed to use mobile app"))


def _ensure_api_credentials(user: Any) -> None:
	"""Generate API credentials if not exists"""
	if not user.api_key or not user.get_password("api_secret"):
		user.api_key = secrets.token_urlsafe(16)
		user.api_secret = secrets.token_urlsafe(32)
		user.save(ignore_permissions=True)


def _generate_auth_token(user: Any) -> str:
	"""Generate encrypted authentication token"""
	api_secret = user.get_password("api_secret")
	return encode_api_credentials(user.api_key, api_secret)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=get_mobile_login_ratelimit, seconds=60 * 60)
def login(username: str | None = None, password: str | None = None) -> dict[str, str]:
	"""Mobile app login handler"""
	try:
		user = _authenticate_user(username, password)
		_validate_mobile_user_role()
		_ensure_api_credentials(user)
		token = _generate_auth_token(user)

		frappe.local.login_manager.logout()

		return {"message": _("Logged In"), "user": user.name, "full_name": user.full_name, "token": token}

	except frappe.AuthenticationError:
		frappe.throw(_("Invalid username or password or user is not allowed to use mobile app"))
	except frappe.PermissionError:
		frappe.throw(_("Not allowed to use mobile app"))
	except Exception as e:
		frappe.log_error(f"Mobile Login Error: {e}")
		frappe.throw(_("Unable to login"))


@frappe.whitelist(methods=["POST"])
def logout() -> dict[str, str]:
	"""Mobile app logout handler"""
	try:
		user = frappe.get_doc("User", frappe.session.user)
		user.api_key = None
		user.api_secret = None
		user.save(ignore_permissions=True)
		return {"message": _("Logged out successfully")}
	except Exception as e:
		frappe.log_error(f"Mobile Logout Error: {e}")
		frappe.throw(_("Unable to logout"))


def _validate_mobile_otp_prerequisites() -> None:
	"""Validate mobile OTP prerequisites"""
	if not is_mobile_otp_login_enabled():
		frappe.throw(_("Mobile OTP login is not enabled"), frappe.AuthenticationError)

	sms_gateway_url = frappe.get_cached_value("SMS Settings", "SMS Settings", "sms_gateway_url")
	if not sms_gateway_url:
		frappe.throw(_("SMS Settings are not configured"), frappe.AuthenticationError)


def _find_user_by_mobile(mobile_no: str) -> dict[str, str]:
	"""Find user by mobile number"""
	if not mobile_no:
		frappe.throw(_("Mobile number is required"), frappe.ValidationError)

	return find_user_by_mobile(mobile_no)


def _send_otp_to_user(user_data: dict, mobile_no: str) -> dict[str, str]:
	"""Send OTP to user and return result"""
	result = send_mobile_login_otp(user_data.name, mobile_no)
	return {
		"message": _("OTP sent successfully"),
		"tmp_id": result.get("tmp_id"),
		"mobile_no": result.get("mobile_no"),
		"prompt": _("Enter verification code sent to {0}").format(result.get("mobile_no", "******")),
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="mobile_no", limit=get_mobile_otp_ratelimit, seconds=60 * 10)
def send_mobile_otp(mobile_no: str) -> dict[str, str]:
	"""Send mobile OTP for authentication"""
	try:
		_validate_mobile_otp_prerequisites()
		validate_phone_number(mobile_no, throw=True)
		user_data = _find_user_by_mobile(mobile_no)
		return _send_otp_to_user(user_data, mobile_no)

	except frappe.AuthenticationError:
		frappe.throw(_("Authentication failed"))
	except frappe.ValidationError:
		frappe.throw(_("Invalid mobile number"))
	except Exception as e:
		frappe.log_error(f"Mobile OTP Send Error: {e}")
		frappe.throw(_("Failed to send OTP. Please try again."))


def _authenticate_with_otp(otp: str, tmp_id: str) -> LoginManager:
	"""Authenticate user with OTP and return login manager"""
	login_manager = LoginManager()
	login_manager._authenticate_mobile_otp(otp, tmp_id)
	login_manager.post_login()
	return login_manager


def _generate_user_token(login_manager: LoginManager) -> tuple[Any, str]:
	"""Generate API credentials and token for authenticated user"""
	user_doc = frappe.get_doc("User", login_manager.user)
	_ensure_api_credentials(user_doc)
	token = _generate_auth_token(user_doc)
	return user_doc, token


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="tmp_id", limit=get_mobile_otp_ratelimit, seconds=60 * 10)
def verify_mobile_otp(tmp_id: str, otp: str) -> dict[str, str]:
	try:
		if not tmp_id or not otp:
			frappe.throw(_("OTP and temporary ID are required"), frappe.ValidationError)

		login_manager = _authenticate_with_otp(otp, tmp_id)
		_validate_mobile_user_role()
		user_doc, token = _generate_user_token(login_manager)
		login_manager.logout()

		return {
			"message": _("Logged In"),
			"user": user_doc.name,
			"full_name": user_doc.full_name,
			"token": token,
		}

	except frappe.AuthenticationError:
		frappe.throw(_("Invalid OTP or session expired"))
	except frappe.ValidationError:
		frappe.throw(_("Invalid request parameters"))
	except Exception as e:
		frappe.log_error(f"Mobile OTP Verify Error: {e}")
		frappe.throw(_("Failed to verify OTP. Please try again."))
