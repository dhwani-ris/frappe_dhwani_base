import hashlib

import frappe
from frappe import _

# Central mapping kept at module-level to keep function size small and mapping easy to extend
FIELD_TYPE_TO_INPUT_TYPE = {
	# Section/Heading breaks -> "10"
	"Section Break": "10",
	"Column Break": "10",
	"Tab Break": "10",
	"Heading": "10",
	# Text inputs -> "1"
	"Data": "1",
	"Small Text": "1",
	"Text": "1",
	"Phone": "1",
	"Password": "1",
	"Barcode": "1",
	"Icon": "1",
	"Signature": "1",
	"Color": "1",
	# Numbers -> "2"
	"Int": "2",
	"Float": "2",
	"Currency": "2",
	"Percent": "2",
	"Duration": "2",
	# Single-select dropdowns -> "3"
	"Select": "3",
	"Link": "3",
	"Autocomplete": "3",
	# Multi-select dropdown -> "4"
	"Table MultiSelect": "4",
	# Rating -> "5"
	"Rating": "5",
	# Checkbox -> "6"
	"Check": "6",
	# Image upload -> "7"
	"Image": "7",
	"Attach Image": "7",
	# File upload -> "11"
	"Attach": "11",
	"File": "11",
	# Date -> "14"
	"Date": "14",
	"Datetime": "14",
	# Address/Location -> "19"
	"Address": "19",
	"Geolocation": "19",
	# Long text/Multi-select -> "20"
	"Long Text": "20",
	"Code": "20",
	"Text Editor": "20",
	"HTML Editor": "20",
	"Table": "20",
}


def _get_field_value(obj, attr, default=None):
	"""Safely get attribute value from object"""
	return getattr(obj, attr, default) if hasattr(obj, attr) else default


def _map_fieldtype_to_input_type(fieldtype, options=None):
	"""Return mForm input_type for a given Frappe fieldtype."""
	return FIELD_TYPE_TO_INPUT_TYPE.get(fieldtype, "1")


def _build_select_autocomplete_options(options, fieldname):
	options_list = [opt.strip() for opt in str(options).split("\n") if opt.strip()]
	result = []
	for idx, option in enumerate(options_list, 1):
		option_id = hashlib.md5(f"{fieldname}_{option}_{idx}".encode()).hexdigest()[:24]
		result.append(
			{
				"_id": option_id,
				"name": option,
				"shortKey": "",
				"visibility": None,
				"did": [],
				"viewSequence": str(idx),
				"coordinates": [],
			}
		)
	return result


def _build_link_options(linked_doctype, fieldname):
	result = []
	try:
		if frappe.db.exists("DocType", linked_doctype):
			linked_meta = frappe.get_meta(linked_doctype)
			title_field = linked_meta.title_field or "name"
			records = frappe.get_all(
				linked_doctype, fields=[title_field, "name"], limit=100, order_by="creation desc"
			)
			for idx, record in enumerate(records, 1):
				display_name = record.get(title_field) or record.get("name", "")
				option_id = hashlib.md5(f"{fieldname}_{record.get('name')}_{idx}".encode()).hexdigest()[:24]
				result.append(
					{
						"_id": option_id,
						"name": display_name,
						"shortKey": "",
						"visibility": None,
						"did": [],
						"viewSequence": str(idx),
						"coordinates": [],
					}
				)
	except Exception:
		pass
	return result


def _build_table_multiselect_options(child_table, fieldname):
	result = []
	try:
		if frappe.db.exists("DocType", child_table):
			child_meta = frappe.get_meta(child_table)
			title_field = child_meta.title_field or "name"
			records = frappe.get_all(
				child_table, fields=[title_field, "name"], limit=100, order_by="creation desc"
			)
			for idx, record in enumerate(records, 1):
				display_name = record.get(title_field) or record.get("name", "")
				option_id = hashlib.md5(f"{fieldname}_{record.get('name')}_{idx}".encode()).hexdigest()[:24]
				result.append(
					{
						"_id": option_id,
						"name": display_name,
						"shortKey": "",
						"visibility": None,
						"did": [],
						"viewSequence": str(idx),
						"coordinates": [],
					}
				)
	except Exception:
		pass
	return result


def _get_answer_options(fieldtype, options, fieldname="", fetch_link_options=False):
	"""Convert Frappe options to answer_option format"""
	if not options:
		return []
	if fieldtype in ("Select", "Autocomplete"):
		return _build_select_autocomplete_options(options, fieldname)
	if fieldtype == "Link" and fetch_link_options:
		return _build_link_options(str(options), fieldname)
	if fieldtype == "Table MultiSelect":
		return _build_table_multiselect_options(str(options), fieldname)
	return []


def _build_validation(field):
	"""Build validation array from field properties with unique _id values"""
	validation = []
	fieldname = _get_field_value(field, "fieldname", "")
	validation_count = 0

	# Required field validation
	if _get_field_value(field, "reqd", False):
		validation_count += 1
		validation_id = hashlib.md5(f"{fieldname}_required_{validation_count}".encode()).hexdigest()[:24]
		validation.append(
			{"_id": validation_id, "error_msg": _get_field_value(field, "error_msg") or "", "condition": None}
		)

	# Depends on validation
	depends_on = _get_field_value(field, "depends_on")
	if depends_on:
		validation_count += 1
		validation_id = hashlib.md5(f"{fieldname}_depends_on_{validation_count}".encode()).hexdigest()[:24]
		validation.append({"_id": validation_id, "error_msg": "", "condition": depends_on})

	# Mandatory depends on
	mandatory_depends_on = _get_field_value(field, "mandatory_depends_on")
	if mandatory_depends_on:
		validation_count += 1
		validation_id = hashlib.md5(
			f"{fieldname}_mandatory_depends_on_{validation_count}".encode()
		).hexdigest()[:24]
		validation.append({"_id": validation_id, "error_msg": "", "condition": mandatory_depends_on})

	# If no validation, return default with unique id
	if not validation:
		validation_id = hashlib.md5(f"{fieldname}_default_validation".encode()).hexdigest()[:24]
		return [{"_id": validation_id, "error_msg": "", "condition": None}]

	return validation


@frappe.whitelist(allow_guest=True)
def get_doctype_metadata(doctype=None):
	"""Return mForm-compatible metadata for a given DocType."""
	if not doctype:
		doctype = frappe.form_dict.get("doctype")
	if not doctype:
		frappe.throw(_("Doctype name is required"), frappe.ValidationError)

	try:
		meta = _validate_and_get_meta(doctype)
		form_id = hashlib.md5(doctype.encode()).hexdigest()[:24]
		questions = _build_questions(meta, doctype)
		return _build_form_response(meta, doctype, questions, form_id)
	except frappe.DoesNotExistError:
		raise
	except Exception:
		frappe.log_error(
			f"Error fetching doctype metadata for {doctype}: {frappe.get_traceback()}",
			title="Doctype Metadata API Error",
		)
		frappe.throw(_("Unable to fetch doctype metadata. Please try again later."))


def _validate_and_get_meta(doctype):
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("Doctype '{0}' does not exist").format(doctype), frappe.DoesNotExistError)
	return frappe.get_meta(doctype)


def _is_section_break(fieldtype):
	return fieldtype in ["Section Break", "Column Break", "Tab Break", "Heading"]


def _build_section_question(field, doctype, idx):
	fieldname = _get_field_value(field, "fieldname", "")
	validation_id = hashlib.md5(f"{fieldname}_section_break_validation".encode()).hexdigest()[:24]
	return {
		"order": str(idx),
		"label": "",
		"title": _get_field_value(field, "label") or fieldname,
		"shortKey": f"order{idx}",
		"information": "",
		"viewSequence": str(idx),
		"input_type": "10",
		"validation": [{"_id": validation_id, "error_msg": "", "condition": None}],
		"answer_option": [],
		"restrictions": [],
		"child": [],
		"parent": [],
		"hint": "",
		"error_msg": "",
		"resource_urls": [],
		"editable": False,
		"weightage": [],
		"_id": hashlib.md5(f"{doctype}_{fieldname}".encode()).hexdigest()[:24],
	}


def _build_regular_question(field, doctype, field_order):
	fieldtype = _get_field_value(field, "fieldtype")
	fieldname = _get_field_value(field, "fieldname", "")
	options = _get_field_value(field, "options")
	input_type = _map_fieldtype_to_input_type(fieldtype, options)
	question = {
		"order": str(field_order),
		"label": str(field_order),
		"title": _get_field_value(field, "label") or fieldname,
		"shortKey": f"order{field_order}",
		"information": "",
		"viewSequence": str(field_order),
		"input_type": input_type,
		"validation": _build_validation(field),
		"answer_option": _get_answer_options(
			fieldtype, options, fieldname, fetch_link_options=(fieldtype == "Table MultiSelect")
		),
		"restrictions": [],
		"isToBeEncrypted": False,
		"child": [],
		"parent": [],
		"hint": _get_field_value(field, "description") or "",
		"error_msg": "",
		"resource_urls": [],
		"editable": not _get_field_value(field, "read_only", False),
		"weightage": [],
		"_id": hashlib.md5(f"{doctype}_{fieldname}".encode()).hexdigest()[:24],
	}
	if fieldtype in ["Int", "Float", "Currency", "Percent"]:
		question["pattern"] = ""
		question["min"] = 1 if _get_field_value(field, "reqd", False) else None
		question["max"] = None
	if "pattern" not in question:
		question["pattern"] = ""
	return question


def _build_questions(meta, doctype):
	questions = []
	field_order = 0
	if hasattr(meta, "fields") and meta.fields:
		for idx, field in enumerate(meta.fields, 1):
			fieldtype = _get_field_value(field, "fieldtype")
			if _is_section_break(fieldtype):
				questions.append(_build_section_question(field, doctype, idx))
				continue
			if _get_field_value(field, "hidden", False) or fieldtype in ["HTML"]:
				continue
			field_order += 1
			questions.append(_build_regular_question(field, doctype, field_order))
	return questions


def _build_form_response(meta, doctype, questions, form_id):
	return {
		"_id": form_id,
		"formId": meta.name,
		"languages": [
			{
				"lng": "en",
				"title": meta.name,
				"buttons": [],
				"question": questions,
				"_id": hashlib.md5(f"{doctype}_en".encode()).hexdigest()[:24],
			}
		],
		"groupOrder": None,
		"keyInfoOrders": [str(i) for i in range(1, min(6, len(questions) + 1))],
		"searchOrders": [str(i) for i in range(1, min(6, len(questions) + 1))],
		"createDynamicOption": [],
		"getDynamicOption": [],
		"projectOrder": 0,
		"projects": [],
		"project": None,
		"organisationId": None,
		"duplicateCheckCopyQuestions": [],
		"childAutoSelection": None,
	}
