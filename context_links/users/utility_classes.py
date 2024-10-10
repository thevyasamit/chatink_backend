from .models import User
from .serializers import UserSerializer
from django.db import transaction
import logging
logger = logging.getLogger(__name__)

class RegisterUserViaSSO:
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    
    def create_user(self,data):
        serializer = self.serializer_class(data=data,partial=True)
        
        with transaction.atomic():
            if serializer.is_valid():
                serializer.save()
                return True
            else:
                logger.error(f"The following error(s) occurred in creating the user {serializer._errors}", exc_info=True)
                return False
            
    