
from django.contrib import admin
from .models import District, Ward, City, Comment, TenantRequest, Image, RentalPost, User, Category, \
    Follow
from django.utils.html import format_html


class CityAdmin(admin.ModelAdmin):
    list_display = ["id","name"]
    search_fields = ["name"]

class WardAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "district_name", "city_name"]  # Hiển thị tên quận và thành phố
    search_fields = ["name"]
    list_filter = ["name", "district__name", "district__city__name"]  # Lọc theo tên quận và tên thành phố

    def district_name(self, obj):
        return obj.district.name if obj.district else 'N/A'  # Trả về tên quận từ mối quan hệ district
    district_name.admin_order_field = 'district__name'  # Sắp xếp theo tên quận
    district_name.short_description = 'District'  # Đặt tên hiển thị cho trường quận

    def city_name(self, obj):
        return obj.district.city.name if obj.district and obj.district.city else 'N/A'  # Trả về tên thành phố từ mối quan hệ city
    city_name.admin_order_field = 'district__city__name'  # Sắp xếp theo tên thành phố
    city_name.short_description = 'City'  # Đặt tên hiển thị cho trường thành phố

class DistrictAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "city_name"]  # Thêm city_name vào list_display
    search_fields = ["name"]
    list_filter = ["name", "city__name"]  # Vẫn có thể lọc theo city__name

    def city_name(self, obj):
        return obj.city.name if obj.city else 'N/A'  # Trả về tên thành phố từ mối quan hệ city
    city_name.admin_order_field = 'city__name'  # Cho phép sắp xếp theo tên thành phố
    city_name.short_description = 'City'  # Đặt tên hiển thị cho trường

class UserAdmin(admin.ModelAdmin):
    list_display = ["username", "first_name", "last_name", "email", ]
    readonly_fields = ["image"]
    def image(self, user):
        if user.avatar:
            return format_html(
                "<img src='/static/{url}' width='100' height='100' />".format(url=user.avatar.name),)

        return "No Avatar"  # Nếu không có avatar, hiển thị thông báo

    def save_model(self, request, obj, form, change):
        if obj.password and not obj.password.startswith('pbkdf2_sha256$'):
            obj.set_password(obj.password)  # Băm mật khẩu nếu chưa được băm
        super().save_model(request, obj, form, change)

admin.site.site_header = "Hệ thống Quản lý Nhà Trọ"
admin.site.site_title = "Admin - Quản lý Nhà Trọ"
admin.site.index_title = "Chào mừng đến với bảng điều khiển Admin"

admin.site.register(Category)
admin.site.register(User,UserAdmin)
admin.site.register(RentalPost)
admin.site.register(TenantRequest)
admin.site.register(Image)
admin.site.register(Comment)
admin.site.register(Follow)
admin.site.register(Ward,WardAdmin)
admin.site.register(City, CityAdmin)
admin.site.register(District, DistrictAdmin)









