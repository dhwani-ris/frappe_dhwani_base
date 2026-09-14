// Copyright (c) 2026, Dhwani RIS and contributors
// For license information, please see license.txt

frappe.ui.form.on("User Manager", {
	refresh(frm) {
		// Force show email field even though it's used for autoname
		if (frm.fields_dict.email) {
			frm.set_df_property("email", "hidden", 0);
			if (frm.fields_dict.email && frm.fields_dict.email.$wrapper) {
				frm.fields_dict.email.$wrapper.show();
			}
		}

		load_role_profiles(frm);
		if (frm.doc.email) {
			fetch_username_from_user(frm);
		}

		render_module_checkboxes(frm);
		setup_program_access_link_filter(frm);
	},

	module_profile(frm) {
		if (frm.doc.module_profile) {
			frappe.call({
				method: "dhwani_frappe_base.dhwani_frappe_base.doctype.user_manager.user_manager.get_module_profile",
				args: { module_profile: frm.doc.module_profile },
				callback: function (data) {
					frm.set_value("block_modules", []);
					(data.message || []).forEach(function (row) {
						let d = frm.add_child("block_modules");
						d.module = row.module;
					});
					frm.dirty();
					frm.refresh_field("block_modules");
					render_module_checkboxes(frm);
				},
			});
		} else {
			frm.set_value("block_modules", []);
			frm.refresh_field("block_modules");
			render_module_checkboxes(frm);
		}
	},

	modules_html(frm) {
		setup_module_checkbox_listeners(frm);
	},

	email(frm) {
		fetch_username_from_user(frm);
	},

	role_profile_html(frm) {
		setup_checkbox_listeners(frm);
	},
});

// Filters the "For Value" (Dynamic Link) options in the Program Access table:
// if a row's doctype (e.g. District) has a Link field to another doctype already
// selected elsewhere in the table (e.g. State), only records belonging to that
// value are offered - e.g. picking State = Delhi restricts District to Delhi's
// districts. Server-side enforcement of the same rule lives in
// UserManager._validate_program_access_hierarchy, so this is UX only.
frappe.ui.form.on("Program Access", {
	program(frm, cdt, cdn) {
		// The set of valid "For Value" options changes with the doctype, so any
		// previously picked value is no longer guaranteed valid.
		frappe.model.set_value(cdt, cdn, "project", "");

		const row = locals[cdt][cdn];
		if (row.program) {
			// Needed synchronously by get_program_access_filters below.
			frappe.model.with_doctype(row.program);
		}
	},
	project(frm, cdt, cdn) {
		reconcile_program_access_table(frm, cdn);
	},
});

let role_profile_link_field = null;

function fetch_username_from_user(frm) {
	if (!frm.doc.email) {
		if (frm.doc.username) {
			frm.set_value("username", "");
		}
		return;
	}

	frappe.call({
		method: "dhwani_frappe_base.dhwani_frappe_base.doctype.user_manager.user_manager.get_username_from_user",
		args: {
			email: frm.doc.email,
		},
		callback: function (r) {
			if (r && r.message && r.message.username) {
				frm.set_value("username", r.message.username);
			} else {
				frm.set_value("username", "");
			}
		},
		error: function (err) {
			frm.set_value("username", "");
		},
	});
}

function get_link_field_name(frm) {
	if (role_profile_link_field) return role_profile_link_field;

	if (frm.meta && frm.meta.fields) {
		let role_profiles_field = frm.meta.fields.find((f) => f.fieldname === "role_profiles");
		if (role_profiles_field && role_profiles_field.options) {
			let child_meta = frappe.get_meta(role_profiles_field.options);
			if (child_meta && child_meta.fields) {
				let link_field_obj = child_meta.fields.find(
					(f) =>
						f.fieldtype === "Link" &&
						(f.options === "Role Profile" || f.options === "User Role Profile")
				);
				if (link_field_obj) {
					role_profile_link_field = link_field_obj.fieldname;
					return role_profile_link_field;
				}
			}
		}
	}

	if (frm.doc.role_profiles && frm.doc.role_profiles.length > 0) {
		let first_row = frm.doc.role_profiles[0];
		if (first_row.role_profile) {
			role_profile_link_field = "role_profile";
		} else if (first_row.user_role_profile) {
			role_profile_link_field = "user_role_profile";
		} else {
			for (let key in first_row) {
				if (key !== "name" && key !== "idx" && first_row[key]) {
					role_profile_link_field = key;
					break;
				}
			}
		}
	}

	if (!role_profile_link_field) {
		role_profile_link_field = "role_profile";
	}

	return role_profile_link_field;
}

function load_role_profiles(frm) {
	role_profile_link_field = null;
	if (!frm.fields_dict.role_profile_html) {
		return;
	}
	frappe.call({
		method: "dhwani_frappe_base.dhwani_frappe_base.doctype.user_manager.user_manager.get_all_role_profiles",
		callback: function (r) {
			let all_role_profiles = r.message || [];
			if (all_role_profiles.length === 0) {
				frm.set_df_property(
					"role_profile_html",
					"options",
					`
					<div style="
						padding: 15px;
						text-align: center;
						color: #888;
						font-style: italic;
					">
						No Role Profile Created
					</div>
				`
				);
				return;
			}
			let profiles = all_role_profiles.map((name) => ({ name: name, _display_name: name }));
			render_checkboxes(frm, profiles, "name");
		},
	});
}

function render_checkboxes(frm, profiles, display_field) {
	let selected_profiles = [];
	if (frm.doc.role_profiles && frm.doc.role_profiles.length > 0) {
		let link_field = get_link_field_name(frm);
		selected_profiles = frm.doc.role_profiles.map((row) => row[link_field]).filter(Boolean);
	}

	let html = generate_checkbox_html(profiles, selected_profiles, display_field);
	if (frm.fields_dict.role_profile_html && frm.fields_dict.role_profile_html.$wrapper) {
		frm.fields_dict.role_profile_html.$wrapper.html(html);
		setup_checkbox_listeners(frm);
	} else {
		frm.set_df_property("role_profile_html", "options", html);
		frm.refresh_field("role_profile_html");
	}
}

function generate_checkbox_html(profiles, selected_profiles, display_field) {
	let html = `
		<div class="role-profile-checkboxes" style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; padding: 10px;">
	`;

	profiles.forEach((profile) => {
		let checked = selected_profiles.includes(profile.name) ? "checked" : "";
		let display_name = profile._display_name || profile[display_field] || profile.name;

		html += `
			<label style="display: flex; align-items: center; cursor: pointer; padding: 2px;">
				<input type="checkbox"
					class="role-profile-checkbox"
					data-profile="${frappe.utils.escape_html(profile.name)}"
					${checked}
					style="margin-right: 8px; cursor: pointer;">
				<span>${frappe.utils.escape_html(display_name)}</span>
			</label>
		`;
	});

	html += `</div>`;
	return html;
}

function setup_checkbox_listeners(frm) {
	$(".role-profile-checkbox").off("change");
	$(".role-profile-checkbox").on("change", function () {
		update_role_profiles_field(frm);
	});
}

function update_role_profiles_field(frm) {
	let selected_profiles = [];
	$(".role-profile-checkbox:checked").each(function () {
		selected_profiles.push($(this).data("profile"));
	});

	let link_field = get_link_field_name(frm);
	let current_profiles = [];
	if (frm.doc.role_profiles && frm.doc.role_profiles.length > 0) {
		current_profiles = frm.doc.role_profiles.map((row) => row[link_field]).filter(Boolean);
	}

	let profiles_changed =
		JSON.stringify(current_profiles.sort()) !== JSON.stringify(selected_profiles.sort());

	if (profiles_changed) {
		let profiles_to_remove = [];
		if (frm.doc.role_profiles) {
			frm.doc.role_profiles.forEach((row, idx) => {
				let profile_value = row[link_field];
				if (profile_value && !selected_profiles.includes(profile_value)) {
					profiles_to_remove.push(idx);
				}
			});

			if (profiles_to_remove.length > 0) {
				let field = frm.get_field("role_profiles");
				let use_grid =
					field && field.grid && field.grid.grid_rows && field.grid.grid_rows.length > 0;

				profiles_to_remove.reverse().forEach((idx) => {
					if (frm.doc.role_profiles && frm.doc.role_profiles[idx]) {
						let row_doc = frm.doc.role_profiles[idx];
						if (
							use_grid &&
							idx < field.grid.grid_rows.length &&
							field.grid.grid_rows[idx]
						) {
							field.grid.grid_rows[idx].remove();
						}
						frappe.model.clear_doc(row_doc.doctype, row_doc.name);
						frm.doc.role_profiles.splice(idx, 1);
					}
				});
			}
		}

		selected_profiles.forEach((profile_name) => {
			let exists = false;
			if (frm.doc.role_profiles) {
				exists = frm.doc.role_profiles.some((row) => row[link_field] === profile_name);
			}
			if (!exists) {
				let row = frm.add_child("role_profiles");
				row[link_field] = profile_name;
			}
		});

		frm.dirty();
		frm.refresh_field("role_profiles");
	}
}

function get_all_modules_then_render(frm, callback) {
	let all_modules = (frm.doc.__onload && frm.doc.__onload.all_modules) || [];
	if (all_modules.length > 0) {
		callback(all_modules);
		return;
	}
	frappe.call({
		method: "dhwani_frappe_base.dhwani_frappe_base.doctype.user_manager.user_manager.get_all_modules",
		callback: function (r) {
			all_modules = r.message || [];
			if (!frm.doc.__onload) {
				frm.doc.__onload = {};
			}
			frm.doc.__onload.all_modules = all_modules;
			callback(all_modules);
		},
	});
}

function render_module_checkboxes(frm) {
	if (!frm.fields_dict.modules_html || !frm.fields_dict.modules_html.$wrapper) {
		return;
	}
	get_all_modules_then_render(frm, function (all_modules) {
		if (all_modules.length === 0) {
			frm.fields_dict.modules_html.$wrapper.html(`
				<div style="padding: 15px; text-align: center; color: #888; font-style: italic;">
					No modules available
				</div>
			`);
			return;
		}
		let block_list = (frm.doc.block_modules || []).map(function (row) {
			return row.module;
		});
		let disabled = frm.doc.module_profile ? "disabled" : "";
		let html = `
			<div class="module-profile-checkboxes" style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; padding: 10px;">
		`;
		all_modules.forEach(function (module_name) {
			let checked = block_list.indexOf(module_name) === -1 ? "checked" : "";
			html += `
				<label style="display: flex; align-items: center; cursor: pointer; padding: 2px;">
					<input type="checkbox"
						class="module-profile-checkbox"
						data-module="${frappe.utils.escape_html(module_name)}"
						${checked}
						${disabled}
						style="margin-right: 8px; cursor: pointer;">
					<span>${frappe.utils.escape_html(module_name)}</span>
				</label>
			`;
		});
		html += `</div>`;
		frm.fields_dict.modules_html.$wrapper.html(html);
		setup_module_checkbox_listeners(frm);
	});
}

function setup_module_checkbox_listeners(frm) {
	$(".module-profile-checkbox").off("change");
	$(".module-profile-checkbox").on("change", function () {
		update_block_modules_from_checkboxes(frm);
	});
}

function update_block_modules_from_checkboxes(frm) {
	if (frm.doc.module_profile) {
		return;
	}
	let blocked = [];
	$(".module-profile-checkbox").each(function () {
		if (!$(this).prop("checked")) {
			blocked.push($(this).data("module"));
		}
	});
	frm.doc.block_modules = [];
	blocked.forEach(function (module_name) {
		let row = frm.add_child("block_modules");
		row.module = module_name;
	});
	frm.dirty();
	frm.refresh_field("block_modules");
}

function setup_program_access_link_filter(frm) {
	frm.set_query("project", "table_fkmn", (doc, cdt, cdn) =>
		get_program_access_filters(frm, cdn)
	);

	// Pre-fetch metas for doctypes already selected (e.g. on opening an existing
	// document) so the filter above can resolve them synchronously.
	(frm.doc.table_fkmn || []).forEach((row) => {
		if (row.program) frappe.model.with_doctype(row.program);
	});
}

function get_sibling_values_by_program(frm, exclude_cdn) {
	const values_by_program = {};
	(frm.doc.table_fkmn || []).forEach((row) => {
		if (row.name === exclude_cdn || !row.program || !row.project) return;
		if (!values_by_program[row.program]) values_by_program[row.program] = [];
		if (!values_by_program[row.program].includes(row.project)) {
			values_by_program[row.program].push(row.project);
		}
	});
	return values_by_program;
}

function get_program_access_filters(frm, cdn) {
	const row = locals["Program Access"][cdn];
	if (!row || !row.program) return {};

	const meta = frappe.get_meta(row.program);
	if (!meta) return {};

	const sibling_values_by_program = get_sibling_values_by_program(frm, cdn);

	const filters = {};
	(meta.fields || [])
		.filter((field) => field.fieldtype === "Link" && field.options)
		.forEach((field) => {
			const values = sibling_values_by_program[field.options];
			if (values && values.length) {
				filters[field.fieldname] = ["in", values];
			}
		});

	return { filters };
}

function reconcile_program_access_table(frm, changed_cdn) {
	const rows = frm.doc.table_fkmn || [];

	rows.forEach((row) => {
		if (!row.program || !row.project) return;

		frappe.model.with_doctype(row.program, () => {
			const meta = frappe.get_meta(row.program);
			const link_fields = (meta.fields || []).filter(
				(field) => field.fieldtype === "Link" && field.options
			);
			if (!link_fields.length) return;

			const sibling_values_by_program = get_sibling_values_by_program(frm, row.name);

			link_fields.forEach((field) => {
				const allowed_values = sibling_values_by_program[field.options];
				if (!allowed_values || !allowed_values.length) return;

				frappe.db
					.get_value(row.program, row.project, field.fieldname)
					.then(({ message }) => {
						const current_value = message && message[field.fieldname];
						if (current_value && !allowed_values.includes(current_value)) {
							frappe.model.set_value(row.doctype, row.name, "project", "");
							frappe.show_alert({
								message: __(
									"Cleared {0} value {1}: it no longer belongs to the selected {2}",
									[__(row.program), row.project, __(field.options)]
								),
								indicator: "orange",
							});
						}
					});
			});
		});
	});
}
