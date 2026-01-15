// Copyright (c) 2026, Dhwani RIS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Dhwani User Management", {
	refresh(frm) {
		load_role_profiles(frm);
		if (frm.doc.email) {
			setTimeout(() => {
				fetch_username_from_user(frm);
			}, 100);
		}
	},
	
	email(frm) {
		fetch_username_from_user(frm);
	},
	
	role_profile_html(frm) {
		if (frm.doc.role_profile_html) {
			setup_checkbox_listeners(frm);
		}
	}
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
		method: "dhwani_frappe_base.dhwani_frappe_base.doctype.dhwani_user_management.dhwani_user_management.get_username_from_user",
		args: {
			email: frm.doc.email
		},
		callback: function(r) {
			if (r && r.message && r.message.username) {
				frm.set_value("username", r.message.username);
			} else {
				frm.set_value("username", "");
			}
		},
		error: function(err) {
			console.log("Error fetching username:", err);
			frm.set_value("username", "");
		}
	});
}

function get_link_field_name(frm) {
	if (role_profile_link_field) return role_profile_link_field;
	
	if (frm.meta && frm.meta.fields) {
		let role_profiles_field = frm.meta.fields.find(f => f.fieldname === 'role_profiles');
		if (role_profiles_field && role_profiles_field.options) {
			let child_meta = frappe.get_meta(role_profiles_field.options);
			if (child_meta && child_meta.fields) {
				let link_field_obj = child_meta.fields.find(f => 
					f.fieldtype === 'Link' && (f.options === 'Role Profile' || f.options === 'User Role Profile')
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
			role_profile_link_field = 'role_profile';
		} else if (first_row.user_role_profile) {
			role_profile_link_field = 'user_role_profile';
		} else {
			for (let key in first_row) {
				if (key !== 'name' && key !== 'idx' && first_row[key]) {
					role_profile_link_field = key;
					break;
				}
			}
		}
	}
	
	if (!role_profile_link_field) {
		role_profile_link_field = 'role_profile';
	}
	
	return role_profile_link_field;
}

function load_role_profiles(frm) {
	role_profile_link_field = null;
	
	frappe.model.with_doctype("Role Profile", () => {
		let meta = frappe.get_meta("Role Profile");
		let title_field = meta.title_field || "name";
		
		let data_fields = meta.fields
			.filter(f => ["Data", "Small Text", "Text"].includes(f.fieldtype))
			.map(f => f.fieldname)
			.filter(f => f !== "name");
		
		let fields_to_fetch = ["name"];
		if (title_field !== "name") {
			fields_to_fetch.push(title_field);
		}
		
		let common_fields = ["role", "role_name", "title", "profile_name"];
		common_fields.forEach(field => {
			if (meta.fields.find(f => f.fieldname === field) && !fields_to_fetch.includes(field)) {
				fields_to_fetch.push(field);
			}
		});
		
		data_fields.slice(0, 3).forEach(field => {
			if (!fields_to_fetch.includes(field)) {
				fields_to_fetch.push(field);
			}
		});
		
		frappe.db.get_list("Role Profile", {
			fields: fields_to_fetch,
			order_by: (title_field !== "name" ? title_field : "name") + " asc"
		}).then(profiles => {
			if (profiles.length === 0) {
				render_checkboxes(frm, [], "name");
				return;
			}
			
			let display_field = title_field;
			if (title_field === "name" || !profiles[0][title_field] || profiles[0][title_field] === profiles[0].name) {
				for (let field of fields_to_fetch) {
					if (field !== "name" && 
					    profiles[0][field] && 
					    typeof profiles[0][field] === "string" && 
					    profiles[0][field].trim() && 
					    profiles[0][field] !== profiles[0].name) {
						display_field = field;
						break;
					}
				}
			}
			
			profiles.forEach(profile => {
				profile._display_name = profile[display_field] || profile.name;
			});
			
			render_checkboxes(frm, profiles, display_field);
		}).catch(err => {
			console.error("Error loading role profiles:", err);
			frappe.db.get_list("Role Profile", {
				fields: ["name"],
				order_by: "name asc"
			}).then(profiles => {
				profiles.forEach(profile => {
					profile._display_name = profile.name;
				});
				render_checkboxes(frm, profiles, "name");
			});
		});
	});
}

function render_checkboxes(frm, profiles, display_field) {
	let selected_profiles = [];
	if (frm.doc.role_profiles && frm.doc.role_profiles.length > 0) {
		let link_field = get_link_field_name(frm);
		selected_profiles = frm.doc.role_profiles.map(row => row[link_field]).filter(Boolean);
	}
	
	let html = generate_checkbox_html(profiles, selected_profiles, display_field);
	frm.set_df_property("role_profile_html", "options", html);
	
	setTimeout(() => {
		setup_checkbox_listeners(frm);
	}, 100);
}

function generate_checkbox_html(profiles, selected_profiles, display_field) {
	let html = `
		<div class="role-profile-checkboxes" style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; padding: 10px;">
	`;
	
	profiles.forEach(profile => {
		let checked = selected_profiles.includes(profile.name) ? 'checked' : '';
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
	$('.role-profile-checkbox').off('change');
	$('.role-profile-checkbox').on('change', function() {
		update_role_profiles_field(frm);
	});
}

function update_role_profiles_field(frm) {
	let selected_profiles = [];
	$('.role-profile-checkbox:checked').each(function() {
		selected_profiles.push($(this).data('profile'));
	});
	
	let link_field = get_link_field_name(frm);
	let current_profiles = [];
	if (frm.doc.role_profiles && frm.doc.role_profiles.length > 0) {
		current_profiles = frm.doc.role_profiles
			.map(row => row[link_field])
			.filter(Boolean);
	}
	
	let profiles_changed = JSON.stringify(current_profiles.sort()) !== JSON.stringify(selected_profiles.sort());
	
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
				let field = frm.get_field('role_profiles');
				let use_grid = field && field.grid && field.grid.grid_rows && field.grid.grid_rows.length > 0;
				
				profiles_to_remove.reverse().forEach(idx => {
					if (frm.doc.role_profiles && frm.doc.role_profiles[idx]) {
						let row_doc = frm.doc.role_profiles[idx];
						if (use_grid && idx < field.grid.grid_rows.length && field.grid.grid_rows[idx]) {
							field.grid.grid_rows[idx].remove();
						}
						frappe.model.clear_doc(row_doc.doctype, row_doc.name);
						frm.doc.role_profiles.splice(idx, 1);
					}
				});
			}
		}
		
		selected_profiles.forEach(profile_name => {
			let exists = false;
			if (frm.doc.role_profiles) {
				exists = frm.doc.role_profiles.some(row => row[link_field] === profile_name);
			}
			if (!exists) {
				let row = frm.add_child('role_profiles');
				row[link_field] = profile_name;
			}
		});
		
		frm.dirty();
		frm.refresh_field('role_profiles');
	}
}

