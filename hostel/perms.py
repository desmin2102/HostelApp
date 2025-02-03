from rest_framework import permissions


class IsTenantRequestOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return hasattr(obj, 'tenant') and obj.tenant == request.user


class IsRentalPostOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return hasattr(obj, 'owner') and obj.owner == request.user


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'admin'


class IsStaffUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'staff'

class IsOwnerUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'owner'


class IsTenantUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'tenant'