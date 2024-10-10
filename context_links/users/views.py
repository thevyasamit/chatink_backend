import logging
import random
import os
import requests
from bs4 import BeautifulSoup
from .models import UserLinks, User, Context
from .serializers import *
from dotenv import load_dotenv
from .utility_classes import *
from django.db.models import Q
from django.shortcuts import render
from rest_framework.views import APIView
from django.http import HttpResponseRedirect
from rest_framework import viewsets, permissions, status
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import APIException
from google.auth.transport import requests as google_requests
from django.shortcuts import redirect
from google.oauth2 import id_token
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from django.middleware.csrf import get_token
import re
from rest_framework.exceptions import Throttled


logger = logging.getLogger(__name__)


# Get the path to the directory where manage.py is located
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load the .env file
load_dotenv(os.path.join(BASE_DIR, '.env'))

GOOGLE_OAUTH_CLIENT_ID = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI')
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')
TOKEN_URL = os.getenv('GOOGLE_TOKEN_URL')
GROQ_KEY = os.getenv('GROQ_API_KEY')
CHAT= ChatGroq(temperature=0, model_name="mixtral-8x7b-32768")


class Index(APIView):
    
    def get(self,request):
        return render(request, 'users/index.html')
        
class UserInfo(APIView):
    
    user_register_obj = RegisterUserViaSSO()
    
    def get(self, request):
        code = request.GET.get('code')
        token_url = TOKEN_URL
        token_data = {
            'code': code,
            'client_id': GOOGLE_OAUTH_CLIENT_ID,
            'client_secret': GOOGLE_OAUTH_CLIENT_SECRET ,
            'redirect_uri': GOOGLE_REDIRECT_URI,
            'grant_type': 'authorization_code',
        }
        token_response = requests.post(token_url, data=token_data)
        logger.info(f"token is {token_response.json()}")
        token_json = token_response.json()
        id_info = id_token.verify_oauth2_token(token_json['id_token'], google_requests.Request(), GOOGLE_OAUTH_CLIENT_ID)
        logger.info(f"the id_info is {id_info}")
        if id_info:
            user_email = id_info.get('email',None)
            given_name = id_info.get('given_name', None)
            family_name = id_info.get('family_name', None)
        
        if not User.objects.filter(email=user_email).exists():
            create_user_data = {"email": user_email, "first_name":given_name,"last_name": family_name}
            if not self.user_register_obj.create_user(data=create_user_data):
                response = HttpResponseRedirect('/api/loginError.html/')  
                return response
        else:
            logger.info(f"the user already exists! {type(user_email)}")
        
        response = HttpResponseRedirect('/api/index/')  
        response.set_cookie('user_email', user_email, secure=True, httponly=True, samesite='Lax')
        response.set_cookie('user_first_name', given_name, secure=True, httponly=True, samesite='Lax')
        response.set_cookie('user_last_name', family_name, secure=True, httponly=True, samesite='Lax')
        
        csrf_token = get_token(request)
        response.set_cookie('csrftoken', csrf_token, secure=True, httponly=True, samesite='Lax')

        request.session.save()
        session_key = request.session.session_key
        response.set_cookie('sessionid', session_key, secure=True, httponly=True, samesite='Lax')
        
        return response
    

# Create your views here.
class UsersView(viewsets.ModelViewSet):
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    @action(detail=False, methods=["POST"])
    def delete_account(self, request):
        user_email = request.data.get('email')
        email = user_email.strip('"')
        logger.info(f"the user email is{email}")
        try:
            delete_obj = User.objects.filter(email=email).first()
            if delete_obj:
                delete_obj.delete()
                return Response(data={"Success": "User Deleted!"},status=status.HTTP_200_OK)
            else:
                return Response(data={"Error": "User not found!"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"The following exception occurred {e}", exc_info=True)
            return Response(data={"Error": "Internal Server Error while deleting the user!"},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    @action(detail=False, methods=["GET"])
    def get_google_sso(self, request):

        url = (
        'https://accounts.google.com/o/oauth2/auth'
        '?response_type=code'
        '&client_id={client_id}'
        '&redirect_uri={redirect_uri}'
        '&scope=openid%20email%20profile'
        '&access_type=offline'
        '&prompt=consent'
        ).format(
        client_id=GOOGLE_OAUTH_CLIENT_ID,
        redirect_uri=GOOGLE_REDIRECT_URI
        )
        return redirect(url)
    
    
class UserLinksView(viewsets.ModelViewSet):
    queryset = UserLinks.objects.all()
    serializer_class = UseLinksSerializer
    

    @action(detail=False, methods=["GET"])
    def user_links(self, request):
        try:
            user_email = request.GET.get('email')
            processed_email = user_email.strip('"')
            user = User.objects.get(email=processed_email)
            user_links = self.queryset.filter(user=user).values("id","link","name")
            return Response(data=user_links, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"the exception is {e}", exc_info=True)
            return Response(data={"Error": "Error occurred in fetching links!"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=["POST"])
    def delete_links(self, request):
        logger.info(f"the request is here!")
        del_ids = request.data.get('link_ids')
        logger.info(f'del ids are : {del_ids}')
        if not del_ids:
            return Response(data={"Error": "No link IDs provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Perform the delete operation
        deleted_count, _ = self.queryset.filter(id__in=del_ids).delete()

        # Check if the deletion was successful
        if deleted_count > 0:
            return Response(data={"Success": f"{deleted_count} links deleted!"}, status=status.HTTP_200_OK)
        else:
            return Response(data={"Error": "No links were deleted. Check the provided IDs."}, status=status.HTTP_400_BAD_REQUEST)


    @action(detail=False, methods=["POST"])
    def save_user_link(self, request):
        # raw_body = request.body
        try:
            data = request.data
            logger.info(f"the request is {data}")
            user_email = data.get('email', None)
            
            if not user_email:
                logger.info('hehe')
                return Response(data={"Error": "User email not found in the request payload!"}, status=status.HTTP_400_BAD_REQUEST)
            user_email_ = user_email.strip('"')
            logger.info(f"the user email is {user_email_}")
            user_obj = User.objects.filter(email=user_email_).first()
            if not user_obj:
                logger.info("hihi")
                return Response(data={"Error": "User not found in the database!"}, status=status.HTTP_400_BAD_REQUEST)
            else:
                data.pop('email')
                data['user'] = user_obj.pk
            
            serializer = self.serializer_class(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response(data={"Success": "Saved user link!"}, status=status.HTTP_201_CREATED)
            else:
                logger.error(f"the following error occurred while saving the user link {serializer._errors}",exc_info=True)
                return Response(data={"Error": "Failed to save user link!"}, status=status.HTTP_400_BAD_REQUEST)
        except:
            logger.error(exc_info=True)
            
            
            
    
class UserContextView(viewsets.ModelViewSet):
    queryset = Context.objects.all()
    serializer_class = UserContextSerializer
    
    @action(detail=False, methods=["POST"])
    def create_context(self, request):
        link_ids = request.data.get('link_ids')
        email = request.data.get('email')
        user_email = email.strip('"')
        user = User.objects.get(email=user_email)
        
        links = list(UserLinks.objects.filter(id__in=link_ids, user_id=user.pk).values_list('link', flat=True))
        
        concatenated_content = ""
    
        for link in links:
            try:
                # Fetch the HTML content of the page
                response = requests.get(link)
                response.raise_for_status()  # Ensure the request was successful
                
                # Parse the HTML content using BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract all the text from the HTML
                page_text = soup.get_text(separator=' ', strip=True)
                
                # Concatenate the link with the parsed content
                concatenated_content += f"Link: {link}, Parsed content: {page_text}, "
            except Exception as e:
                concatenated_content += f"Link: {link}, "
                logger.info(f"Failed to process link {link}: {e}")
        context = concatenated_content
        
        user_context_data = {
            "links":link_ids,
            "user": user.pk,
            "context": context
        }
        
        serializer = self.serializer_class(data=user_context_data)
        if serializer.is_valid():
            serializer.save()
            return Response(data={"context_id": serializer.data.get('id')}, status=status.HTTP_201_CREATED)
        else:
            logger.error(f"The errors are {serializer._errors}")
            return Response(data={"Error": "Failed to save user link!"}, status=status.HTTP_400_BAD_REQUEST)
        
        
        
    @action(detail=False, methods=["POST"])
    def chat(self, request):
        
        logger.info("here I am ")
        context_id = request.data.get('context_id')
        human = request.data.get('user_input')

        if not (context_id and human):
            logger.error("Missing context_id or user_input in the request.")
            return Response(data={"Error": "Failed to save user link!"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Fetch the context using the context_id
            context_data = self.queryset.get(id=context_id).context
            logger.info(f"Successfully retrieved context for context_id: {context_id}")
        except self.queryset.model.DoesNotExist:
            logger.error(f"Context with id {context_id} not found.")
            return Response(data={"Error": "Context not found!"}, status=status.HTTP_404_NOT_FOUND)

        # Define the system and human messages
        system_message = ""
        human_message = f""

        # Construct the chat prompt template
        prompt = ChatPromptTemplate.from_messages([("system", system_message), ("human", human_message)])

        # Invoke the AI model to get the response
        try:
            ai_response = prompt | CHAT
            response = ai_response.invoke({"text": context_data})
            ai_response = response.content
            logger.info("AI response successfully generated.")
            logger.info(f"the response is {response}, {type(response)}")
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"AI processing failed: {error_message}")
            
            if "Rate limit reached" in error_message and "tokens per minute (TPM)" in error_message:
                # Extract the cooldown time from the error message
                cooldown_match = re.search(r"Please try again in (\d+)m(\d+\.\d+)s", error_message)
                if cooldown_match:
                    minutes, seconds = cooldown_match.groups()
                    cooldown_seconds = int(minutes) * 60 + float(seconds)
                else:
                    cooldown_seconds = 600

                raise Throttled(
                    detail={
                        "error": "Token limit reached. Please try again later.",
                        "cooldown_period": "10 minutes",
                        "retry_after": int(cooldown_seconds)
                    },
                    wait=int(cooldown_seconds)
                )
            else:
                return Response(
                    data={"Error": f"AI processing failed: {error_message}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # Return the AI's response
        logger.info("Returning AI response to the client.")
        return Response(data={"ai_response": ai_response}, status=status.HTTP_200_OK)


    @action(detail=False, methods=["POST"])
    def page_summary(self, request):

        request_link = request.data.get('link')
        concatenated_content = ""

        try:
            # Fetch the HTML content of the page
            response = requests.get(request_link)
            response.raise_for_status()  # Ensure the request was successful
            
            # Parse the HTML content using BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract all the text from the HTML
            page_text = soup.get_text(separator=' ', strip=True)
            
            # Concatenate the link with the parsed content
            concatenated_content += f"Link: {request_link}, Parsed content: {page_text}, "
        except Exception as e:
            concatenated_content += f"Link: {request_link}, "
            logger.info(f"Failed to process link {request_link}: {e}")

        context = concatenated_content

        # Define the system and human messages
        system_message = ""
        human_message = f""

        # Construct the chat prompt template
        prompt = ChatPromptTemplate.from_messages([("system", system_message), ("human", human_message)])

        # Invoke the AI model to get the response
        try:
            ai_response = prompt | CHAT
            response = ai_response.invoke({"text": context})
            ai_response = response.content
            logger.info("AI response successfully generated.")
            logger.info(f"the response is {response}, {type(response)}")
        except Exception as e:
            error_message = str(e)
            logger.error(f"AI processing failed: {error_message}")
            
            if "Rate limit reached" in error_message and "tokens per minute (TPM)" in error_message:
                # Extract the cooldown time from the error message
                cooldown_match = re.search(r"Please try again in (\d+)m(\d+\.\d+)s", error_message)
                if cooldown_match:
                    minutes, seconds = cooldown_match.groups()
                    cooldown_seconds = int(minutes) * 60 + float(seconds)
                else:
                    cooldown_seconds = 600  # Default to 10 minutes if we can't parse the time

                return Response(
                    {
                        "error": "Token limit reached. Please try again later.",
                        "cooldown_period": "10 minutes",
                        "retry_after": int(cooldown_seconds)
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )
            else:
                return Response(
                    data={"Error": f"AI processing failed: {error_message}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # Return the AI's response
        logger.info("Returning AI response to the client.")
        return Response(data={"ai_response": ai_response}, status=status.HTTP_200_OK)
