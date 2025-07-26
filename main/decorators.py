from functools import wraps
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse
from main.models import *
import sweetify


def client_facing_login_required(function):
  @wraps(function)
  def wrap(request, *args, **kwargs):
        if request.user.is_authenticated:
            return function(request, *args, **kwargs)
        else:
            sweetify.error(request, 'You must be logged in to view this page.', button='Login')
            return redirect('landingpage')
  return wrap





