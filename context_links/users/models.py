from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager

class UserProfileManager(BaseUserManager):
    def create_user(self, email, first_name, last_name, password=None):
        if not email:
            raise ValueError("Users must have an email address")
        
        email = self.normalize_email(email)
        user = self.model(email=email, first_name=first_name, last_name=last_name)
        
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, first_name, last_name, password=None):
        user = self.create_user(email, first_name, last_name, password)
        user.is_admin = True
        user.save(using=self._db)
        return user

class User(AbstractBaseUser):
    email = models.EmailField(max_length=255, unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)

    objects = UserProfileManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

    @property
    def is_staff(self):
        return self.is_admin
    

class UserLinks(models.Model):
    name = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    link = models.URLField()
    created_on = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.name
    
    
class Context(models.Model):
    created_on = models.DateField(auto_now_add=True)
    links = models.ManyToManyField(UserLinks)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    context = models.TextField()
    
    
    def __str__(self):
        return f"{self.pk} - {self.user}"
    
