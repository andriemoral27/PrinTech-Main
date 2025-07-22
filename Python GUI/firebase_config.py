import firebase_admin
from firebase_admin import credentials, db
import os

# Path to the service account key JSON file
SERVICE_ACCOUNT_KEY = {
    "type": "service_account",
    "project_id": "printech-bd2ca",
    "private_key_id": "ccd5e448e9e16e95ca03a3fe96dfe68d4ce33f6b",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQDg6GK8r1uU1we/\nd7Wt22Lc8dTpyMtYrEyynT1tPd+uNr3MmTSOs7dHZlvsFXp1BJ01tKxIxHzLqjCS\nnj/yJVQPppPAObgYXxZT8ihT0qSq5LGSH1E6SKxBng3O8uXVRjL/Gif2OWQPxPF3\n3OpEt5mFdeLEnqlJqanJpHvOQv2UC5UcG3phvGTxTcW0FJc5hvF+iYnunjywUzcD\nkObTgTI5x8Bo/W+LwY8mdd+qeGPzX3GDx2bojgw1YLr2NrxitVSfXmG6zeqJFkKO\njJcN9lXyD5ZulVt7BJMCQnisrsrS7BnN/VeDKEu+G07yimaIRK+sWteqcBTGzZ58\nnoKZ9UazAgMBAAECggEACeaQ+idqC6pPoAEgEVA4EOvgaI47TWMAWViMrLNtlli4\nkDoqUyHcLpt17nWfl2klloimkOl9aOXMD5hBzmIQSkQV+v9PeFsvO3DMj6wVLaS1\noG4agEtUserIRtTwgyv88LfxDGjIW91al+E0uuOuMW7YFbm6UBDU9Zh1DsZqLUsk\nFposTBriaxjxY8a1ARBpCtPVNKj8Id1uGVtnYE6OyGKXZ3uL6R6VVtV0EAvJvhk3\n4111z3Lkl+a8DHa6xQ4oXGczb84tARLGL1h3CY56hIdqOGVLt5YKYi8xoLHd/8TW\n+5WRBO+SA64r58rICSNnru/wtG1eUgzp0UhMWHUX6QKBgQD650/ZoSBhYw9wnMJy\nnGDjTHtJ1o6KqbohpebcmsUhau3N0UInZCfucXfyL7G+kX0uKvFyexCvsHquPIZ4\nzz4ijTN3quPWG0UlRZ3VbsGEPcHGkyDOq8ZV72TlzkHanrQtOh9L5zUejW8yR8Co\ndAadwOXtKs0Elp+fxMbxy1l4rwKBgQDleeWMJCdesBuuvPrvqNMq7K0VMPqYTlWl\n7w5VfpMmpFBtZSg2nWVpNfEotcxBTK3/21VzgQmlvl6lEMHQD/eO1nzrZINXfYrm\n9/LklN4Hp4g4wjVzFkCjGUq79oR67cb8mdpD0o7pG7biuf1QDhSli00xzwxTPAyk\ndRpqfswLPQKBgQC9F/emHTk6LF5GkN47Yn/izpFcZMeo2aHeGhqTyFEpjl0K8Nra\ntTEjE4FClY9wAFZHpTWzAezhfC/5gMQX6Jj7kU9osPJlOsgx/vWlFYPjFmgkMF5Z\nZDxmJ7XzPC+FhHZmX5eWrPnrvMxBKLKaQld6LRccV1WMT7idwL/vG0KjIQKBgQCI\n4Eumas488YihksGPAEFs4h1ffYaMIHV/83a2UjiNnQcIKYVyBjI+Llm5ca7y6D0F\nVxvCOJ67iTDE/pjMdSmxvohmk96v6gdXO2BbLdy97hUX3eepzQUjA+wK78EX3gqK\nE28Yc1ig/NH6rPvGq49vKwcRhbGRWEkmM19dVGJ69QKBgQC263Da+lbo4IRJdwmP\n0w8jtJce7GECtWQ3tAODHAXyeq69qSKa/A98BE1lkyxSup62Q5JjeMrG3+0nmszk\nROg2lvbcGd3NFWCtI5j2DuamJm0vsruEDjmOoGiPG9lFKZWmyHyMBIBVs0A2T8fC\nKg37kKsIWyR/oQmnsn1b/jz3Lg==\n-----END PRIVATE KEY-----\n",
    "client_email": "firebase-adminsdk-fbsvc@printech-bd2ca.iam.gserviceaccount.com",
    "client_id": "107071604968944738059",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40printech-bd2ca.iam.gserviceaccount.com",
    "universe_domain": "googleapis.com"
}

DATABASE_URL = "https://printech-bd2ca-default-rtdb.asia-southeast1.firebasedatabase.app/"

# Initialize Firebase app if not already initialized
if not firebase_admin._apps:
    cred = credentials.Certificate(SERVICE_ACCOUNT_KEY)
    firebase_admin.initialize_app(cred, {
        'databaseURL': DATABASE_URL
    }) 