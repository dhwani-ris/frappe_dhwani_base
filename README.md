# Dhwani Frappe Base

A foundational Frappe app containing reusable components and utilities for rapid development across multiple projects.

## 🚀 Features

### 📍 Geographic Data Management
Complete hierarchical geographic data structure for Indian administrative divisions:

- **State**: State-level administrative data with codes and census codes
- **District**: District-level data linked to states
- **Block**: Block-level administrative units linked to districts  
- **Grampanchayat**: Grampanchayat-level data linked to blocks
- **Village**: Village-level data linked to blocks and grampanchayats

### 🔐 Mobile Authentication System
Secure mobile app authentication with JWT-based token system:

- **Encrypted Token Authentication**: Fernet encryption for secure API credentials
- **Role-based Access Control**: Mobile User role validation
- **Rate Limiting**: Configurable login attempt limits (5 attempts per hour)
- **Token Expiration**: Automatic token expiry management
- **Secure Logout**: API credential reset on logout

### 🌐 API Endpoints
RESTful API endpoints for mobile applications:

- `mobile_login`: Secure login with encrypted token generation
- `mobile_logout`: Logout with credential reset

## 📋 DocTypes

### State
- **Fields**: State Code, State Census Code, State Name
- **Naming**: By state_name field
- **Permissions**: System Manager role

### District  
- **Fields**: State (Link), District Code, District Census Code, District Name
- **Naming**: By district_name field
- **Permissions**: System Manager role

### Block
- **Fields**: District (Link), Block Code, Block Census Code, Block Name
- **Naming**: By block_name field
- **Permissions**: System Manager role

### Grampanchayat
- **Fields**: Block (Link), Grampanchayat Code, Grampanchayat Census Code, Grampanchayat Name
- **Naming**: By grampanchayat_name field
- **Permissions**: System Manager role

### Village
- **Fields**: Block (Link), Grampanchayat (Link), Village Code, Village Census Code, Village Name
- **Naming**: By village_name field
- **Permissions**: System Manager role


## 📦 Installation

### Prerequisites
- Frappe Framework v15+
- Python 3.10+
- Bench CLI

### Install App
```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app dhwani_frappe_base
```

### Post-Installation Setup
1. **Create Mobile User Role**:
   ```python
   # In Frappe console or via API
   frappe.get_doc({
       "doctype": "Role",
       "role_name": "Mobile User",
       "desk_access": 0
   }).insert()
   ```

2. **Assign Role to Users**:
   ```python
   # Add Mobile User role to existing users
   user = frappe.get_doc("User", "user@example.com")
   user.add_roles("Mobile User")
   user.save()
   ```

## 🔌 API Usage

### Login Endpoint
```bash
POST /api/method/mobile_login
Content-Type: application/json

{
    "username": "user@example.com",
    "password": "password123"
}
```

**Response**:
```json
{
    "message": "Logged In",
    "user": "user@example.com", 
    "full_name": "John Doe",
    "token": "encrypted_token_string"
}
```

### Logout Endpoint
```bash
POST /api/method/mobile_logout
Authorization: Bearer encrypted_token_string
```

**Response**:
```json
{
    "message": "Logged out successfully"
}
```

### Using Encrypted Tokens
```bash
GET /api/resource/State
Authorization: Bearer encrypted_token_string
```

## 📊 Database Schema

### Geographic Hierarchy
```
State (1) → District (N) → Block (N) → Grampanchayat (N) → Village (N)
```

### Key Relationships
- District → State (Link Field)
- Block → District (Link Field)  
- Grampanchayat → Block (Link Field)
- Village → Block + Grampanchayat (Link Fields)

## 🔒 Security Considerations

### Data Protection
- All geographic data is read-only for standard users
- Only System Managers can modify geographic data
- API credentials are encrypted at rest
- Tokens have automatic expiration

### Access Control
- Mobile User role required for API access
- Rate limiting prevents abuse
- Comprehensive audit logging
- Secure credential management


## 📝 License

MIT License - see [LICENSE](license.txt) file for details.

## 📞 Support

For support and questions:
- **Email**: bhushan.barbuddhe@dhwaniris.com
- **Organization**: Dhwani RIS

---

**Version**: 1.0.0  
**Last Updated**: January 2025  
**Compatibility**: Frappe Framework v15+