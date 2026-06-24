# Frontend Data Structures Specification

This document details the data structures sent from the backend to render the templates (Context) and sent from the frontend to the backend (Payload/Actions) for the five core user and permission administration pages.

---

## 1. User List Screen
**Purpose:** Displays all registered users and their details with activation/deactivation triggers.

### A. Context (Data Sent to the Page)
The backend passes a list of user objects with profile and defaults:
```json
{
  "users": [
    {
      "id": 2,
      "email": "ahmedmohamedrashed2811@gmail.com",
      "first_name": "Ahmed",
      "last_name": "Rashed",
      "phone": "+201234567890",
      "is_active": true,
      "profile": {
        "job_title": "Senior CRM Engineer",
        "department": "Engineering",
        "availability_status": "AVAILABLE", 
        "availability_status_display": "Available",
        "default_role": {
          "id": 1,
          "name": "System Administrator",
          "code": "SYSTEM_ADMINS"
        }
      }
    }
  ]
}
```

### B. Payload (Actions Sent from the Page)
* **Deactivate User:** Sends a GET or POST request to: `/accounts/users/<id>/delete/`
* **Activate User:** Sends a GET or POST request to: `/accounts/users/<id>/activate/`

---

## 2. User Form (Create / Edit) Screen
**Purpose:** Create a new user profile with inline overrides, or edit an existing user's details.

### A. Context (Data Sent to the Page)
```json
{
  "is_edit_mode": false, 
  "user_instance": null, 
  "roles": [
    { "id": 1, "name": "System Administrator", "code": "SYSTEM_ADMINS" },
    { "id": 2, "name": "Sales Rep", "code": "SALES" }
  ],
  "permissions": [
    {
      "code": "admin.users.access",
      "name": "Open users page",
      "module": "admin",
      "description": "Allows viewing the users list"
    },
    {
      "code": "audit.view_all",
      "name": "View audit log",
      "module": "audit",
      "description": "Allows viewing system audit logs"
    }
  ],
  "role_permissions_json": "{\"1\": [\"admin.users.access\", \"audit.view_all\"], \"2\": [\"admin.users.access\"]}"
}
```
*Note: If `is_edit_mode` is `true`, `user_instance` is passed with a user object, and the permission checklist is hidden and replaced by a matrix redirect link.*

### B. Payload (Form Submit POST Data)
```json
{
  "email": "newuser@example.com",
  "password": "strongpassword123",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1234567890",
  "job_title": "Developer",
  "default_role": "2", 
  "permissions": [
    "admin.users.access",
    "audit.view_all"
  ]
}
```

---

## 3. General Audit Trail Screen
**Purpose:** Display historical system actions, changed fields, and HTTP contexts.

### A. Context (Data Sent to the Page)
A list of audit trail objects:
```json
{
  "page": [
    {
      "id": 105,
      "created_at": "2026-06-24T12:47:00Z",
      "action": "PERMISSION_CHANGE",
      "entity_type": "UserPermissionOverride",
      "entity_id": "2",
      "entity_display": "ahmedmohamedrashed2811@gmail.com",
      "actor": {
        "email": "admin@example.com",
        "full_name": "Super Admin"
      },
      "before_json": {
        "admin.users.access": "ALLOW"
      },
      "after_json": {
        "admin.users.access": "ALLOW",
        "audit.view_all": "ALLOW"
      },
      "changed_fields": {
        "audit.view_all": {
          "old": null,
          "new": "ALLOW"
        }
      },
      "request_meta": {
        "ip": "127.0.0.1",
        "method": "POST",
        "path": "/authorization/users/2/matrix/",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)..."
      },
      "reason": "Customized at user matrix update"
    }
  ]
}
```

### B. Payload (Query parameters sent on filtering)
GET query parameters are sent on filter submission:
* `?action=PERMISSION_CHANGE&entity_type=UserPermissionOverride&page=2`

---

## 4. User Matrix Screen
**Purpose:** View and toggle direct permission overrides (`ALLOW`/`DENY`) away from the default role.

### A. Context (Data Sent to the Page)
```json
{
  "target": {
    "id": 2,
    "email": "ahmedrashed2811@gmail.com",
    "full_name": "Ahmed Rashed",
    "profile": {
      "job_title": "Senior CRM Engineer",
      "department": "Engineering",
      "default_role": {
        "id": 1,
        "name": "System Administrator"
      }
    }
  },
  "permissions": [
    {
      "code": "admin.users.access",
      "name": "Open users page",
      "module": "admin",
      "description": "Allows viewing the users list"
    }
  ],
  "role_permissions_json": "{\"1\": [\"admin.users.access\"]}",
  "user_active_permissions": [
    "admin.users.access",
    "audit.view_all"
  ]
}
```

### B. Payload (POST Data on Save)
An array of all checkbox permission codes that are currently **checked** by the admin:
```json
{
  "permissions": [
    "admin.users.access",
    "audit.view_all"
  ]
}
```

---

## 5. Permission Preview Screen
**Purpose:** Sandbox simulation showing accessible menus and pages for a target user.

### A. Context (Data Sent to the Page)
```json
{
  "target": {
    "id": 2,
    "email": "ahmedrashed2811@gmail.com",
    "full_name": "Ahmed Rashed"
  },
  "effective_codes": [
    "admin.users.access",
    "dashboard.main.access"
  ],
  "permissions": [
    { "code": "admin.users.access", "name": "Open users page", "module": "admin" },
    { "code": "dashboard.main.access", "name": "Open dashboard", "module": "dashboard" }
  ],
  "accessible_pages": [
    { "code": "dashboard.main", "name": "Dashboard", "url_name": "dashboard", "menu_order": 1 },
    { "code": "admin.users", "name": "Users", "url_name": "accounts:user_list", "menu_order": 2 }
  ]
}
```

### B. Payload (Actions Sent from the Page)
* None (this is a read-only preview/simulation screen).
