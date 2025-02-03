from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import  JSONField
from django.urls import reverse
from django.utils.text import slugify
from taggit.managers import TaggableManager


# Abstract Base Model
class ItemBase(models.Model):
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['created_at']


class User(AbstractUser):
    class UserRole(models.TextChoices):
        STAFF = 'staff', 'Staff'
        OWNER = 'owner', 'Owner'
        TENANT = 'tenant', 'Tenant'

    role = models.CharField(
        max_length=10,choices=UserRole.choices, default=UserRole.STAFF,
    )
    avatar = models.ImageField(upload_to='avatarUser/%Y/%m', null=False, blank=False)
    phone_number = models.CharField(max_length=15)


    def __str__(self):
        return self.first_name + " " + self.last_name


# Abstract Post Model
class Post(ItemBase):
    title = models.CharField(max_length=255)
    description = models.TextField(default='')
    category = models.ForeignKey('Category', on_delete=models.CASCADE, null=True, blank=True)
    area = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tags = TaggableManager()

    class Meta:
        abstract = True
        ordering = ['-id']  # Mặc định sắp xếp bài đăng mới nhất lên đầu
    def __str__(self):
        return self.title


# Rental Post (Bài đăng cho thuê)
class RentalPost(Post):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rental_posts',
                              limit_choices_to={'role': User.UserRole.OWNER})
    price = models.IntegerField(null=False, blank=True)
    city = models.ForeignKey('City', on_delete=models.CASCADE, null=False, blank=False)
    district = models.ForeignKey('District', on_delete=models.CASCADE, null=False, blank=False)
    ward = models.ForeignKey('Ward', on_delete=models.CASCADE, null=False, blank=False)
    address = models.CharField(max_length=255, null=False, blank=False)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"Rental Post: {self.title} by {self.owner.username}"

    def get_absolute_url(self):
        return reverse('rentalpost-detail', kwargs={'pk': self.pk})

# Tenant Request (Bài đăng tìm trọ)
class TenantRequest(Post):
    tenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tenant_requests',
                               limit_choices_to={'role': User.UserRole.TENANT})
    min_price = models.IntegerField(null=True, blank=True)
    max_price = models.IntegerField(null=True, blank=True)

    # Chỉ cho phép chọn một thành phố duy nhất
    city = models.ForeignKey('City', on_delete=models.CASCADE)
    # Vẫn cho phép chọn nhiều quận và phường trong thành phố đó
    districts = models.ManyToManyField('District', blank=True)
    wards = models.ManyToManyField('Ward', blank=True)

    def __str__(self):
        return f"Tenant Request: {self.tenant.username} - City: {self.city.name if self.city else 'Not selected'}"

# Category Model
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


# Image Model
class Image(ItemBase):
    rental_post = models.ForeignKey(RentalPost, on_delete=models.CASCADE,related_name='images_rental_post',)
    image = models.ImageField(upload_to="post/%Y/%m")


    def __str__(self):
        return f"Image {self.id} of RentalPost {self.rental_post.id}"


# Location Models
class City(ItemBase):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class District(ItemBase):
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='districts')
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ['city', 'name']  # Đảm bảo tên quận duy nhất trong mỗi thành phố.

    def __str__(self):
        return self.name


class Ward(ItemBase):
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name='wards')
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ['district', 'name']  # Đảm bảo tên phường duy nhất trong mỗi quận.

    def __str__(self):
        return f"{self.name} - {self.district.name}"

# Follow Model (Theo dõi)
class Follow(ItemBase):
    tenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='follows',
                               limit_choices_to={'role': User.UserRole.TENANT})
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers',
                              limit_choices_to={'role': User.UserRole.OWNER})

    class Meta:
        unique_together = ('tenant', 'owner')

    def __str__(self):
        return f"{self.tenant} follows {self.owner}"

class Interaction(ItemBase):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        abstract = True

# Comment - Liên kết với các bài đăng thực tế (RentalPost, TenantRequest)
class Comment(Interaction):
    content = models.TextField(blank=False)
    parent_comment = models.ForeignKey("self", null=True, blank=True, related_name="replies", on_delete=models.CASCADE)

    def __str__(self):
        return f"Comment by {self.user.username} on {self.content_object.__class__.__name__}"

# Like - Liên kết với các bài đăng thực tế (RentalPost, TenantRequest)
class Like(Interaction):
    class Meta:
        unique_together = ('user', 'content_type', 'object_id')  # Đảm bảo một người dùng chỉ like một bài đăng một lần

    def __str__(self):
        return f"Like by {self.user.username} on {self.content_object.__class__.__name__}"

