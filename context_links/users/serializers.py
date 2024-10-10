from rest_framework import serializers
from .models import *

class UserSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = User
        fields = "__all__"


class UseLinksSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = UserLinks
        fields = "__all__"
        

class UserContextSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Context
        fields = "__all__"
