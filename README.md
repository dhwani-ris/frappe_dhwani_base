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
- **Mobile OTP Authentication**: SMS-based OTP verification for passwordless login
- **Role-based Access Control**: Mobile User role validation
- **Rate Limiting**: Configurable login attempt limits (5 attempts per hour)
- **Token Expiration**: Automatic token expiry management
- **Secure Logout**: API credential reset on logout

### 🌐 API Endpoints
RESTful API endpoints for mobile applications:

- `mobile_login`: Secure login with encrypted token generation
- `mobile_logout`: Logout with credential reset
- `send_mobile_otp`: Send OTP to mobile number for authentication
- `verify_mobile_otp`: Verify OTP and authenticate user

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
1. **Enable Mobile OTP Login** (in System Settings):
   - Set `allow_login_using_mobile_number` = 1
   - Set `allow_mobile_login_with_otp` = 1

2. **Configure SMS Settings**:
   - Go to SMS Settings doctype
   - Configure SMS gateway URL and credentials
   - Test SMS delivery

3. **Create Mobile User Role**:
   ```python
   # In Frappe console or via API
   frappe.get_doc({
       "doctype": "Role",
       "role_name": "Mobile User",
       "desk_access": 0
   }).insert()
   ```

4. **Assign Role to Users**:
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

### Send Mobile OTP Endpoint
```bash
POST /api/method/send_mobile_otp
Content-Type: application/json

{
    "mobile_no": "+1234567890"
}
```

**Response**:
```json
{
    "message": "OTP sent successfully",
    "tmp_id": "abc123def",
    "mobile_no": "******7890",
    "prompt": "Enter verification code sent to ******7890"
}
```

### Verify Mobile OTP Endpoint
```bash
POST /api/method/verify_mobile_otp
Content-Type: application/json

{
    "tmp_id": "abc123def",
    "otp": "123456"
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
- Rate limiting prevents abuse (5 attempts per 10 minutes for OTP)
- Comprehensive audit logging
- Secure credential management
- OTP session expiry (5 minutes default)
- Login attempt tracking for security monitoring


## 📝 License

MIT License - see [LICENSE](license.txt) file for details.

## 📞 Support

For support and questions:
- **Email**: bhushan.barbuddhe@dhwaniris.com
- **Organization**: Dhwani RIS

---

**Version**: 1.1.0  
**Last Updated**: January 2025  
**Compatibility**: Frappe Framework v15+

## 🔄 Mobile OTP Authentication Flow

### Step-by-Step Process

1. **Send OTP**: User requests OTP by providing mobile number
2. **Validate Mobile**: System validates mobile number and finds user
3. **Generate OTP**: System generates TOTP token and caches it
4. **Send SMS**: OTP is sent via configured SMS gateway
5. **Verify OTP**: User submits OTP with temporary ID
6. **Authenticate**: System verifies OTP and creates authenticated session
7. **Generate Token**: API credentials and encrypted token are generated
8. **Access APIs**: User can now access protected endpoints with token

### Security Features

- **Rate Limiting**: 5 attempts per mobile number per 10 minutes
- **Session Expiry**: OTP sessions expire after 5 minutes
- **Token Cleanup**: Cached OTP data is deleted after successful verification
- **Login Tracking**: All attempts are logged for security monitoring
- **Mobile Validation**: Phone number format validation
- **User Verification**: Only enabled users with mobile numbers can receive OTP