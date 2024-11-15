from django import forms
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import IntegrityError
from django.forms import modelformset_factory
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import ListView, DeleteView
from django.views.generic.detail import DetailView
from django.utils.decorators import method_decorator

from .forms import FoodForm, ImageForm
from .models import User, Food, FoodCategory, FoodLog, Image, Weight


def index(request):
    '''
    The default route which lists all food items
    '''
    view = FoodListView.as_view()
    return view(request)


def register(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']

        # Ensure password matches confirmation
        password = request.POST['password']
        confirmation = request.POST['confirmation']
        if password != confirmation:
            return render(request, 'register.html', {
                'message': 'Passwords must match.',
                'categories': FoodCategory.objects.all()
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, 'register.html', {
                'message': 'Username already taken.',
                'categories': FoodCategory.objects.all()
            })
        login(request, user)
        return HttpResponseRedirect(reverse('index'))
    else:
        return render(request, 'register.html', {
            'categories': FoodCategory.objects.all()
        })


def login_view(request):
    if request.method == 'POST':

        # Attempt to sign user in
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse('index'))
        else:
            return render(request, 'login.html', {
                'message': 'Invalid username and/or password.',
                'categories': FoodCategory.objects.all()
            })
    else:
        return render(request, 'login.html', {
            'categories': FoodCategory.objects.all()
        })


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse('index'))


class FoodListView(ListView):
    model = Food
    template_name = 'index.html'
    context_object_name = 'foods'
    paginate_by = 4
    foods = Food.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        foods = Food.objects.all()

        # Attach the first image to each food object
        for food in foods:
            food.image = food.get_images.first()

        # Add custom context data
        context['categories'] = FoodCategory.objects.all()
        context['title'] = 'Food List'

        # Manually handle pagination (if you want custom behavior)
        paginator = Paginator(foods, self.paginate_by)
        page = self.request.GET.get('page', 1)
        try:
            context['pages'] = paginator.page(page)
        except PageNotAnInteger:
            context['pages'] = paginator.page(1)
        except EmptyPage:
            context['pages'] = paginator.page(paginator.num_pages)

        return context


@method_decorator(login_required, name='dispatch')
class FoodDetailView(DetailView):
    model = Food
    template_name = 'food.html'
    context_object_name = 'food'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = FoodCategory.objects.all()
        context['images'] = self.object.get_images.all()  # Assuming 'get_images' is a related manager
        return context


class FoodAddView(LoginRequiredMixin, View):
    """
    A view to handle adding a new food item and associated images.
    """
    template_name = 'food_add.html'

    def get(self, request, *args, **kwargs):
        ImageFormSet = modelformset_factory(Image, form=ImageForm, extra=2)
        context = {
            'categories': FoodCategory.objects.all(),
            'food_form': FoodForm(),
            'image_form': ImageFormSet(queryset=Image.objects.none()),
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        ImageFormSet = modelformset_factory(Image, form=ImageForm, extra=2)
        food_form = FoodForm(request.POST, request.FILES)
        image_form = ImageFormSet(request.POST, request.FILES, queryset=Image.objects.none())

        if food_form.is_valid() and image_form.is_valid():
            new_food = food_form.save(commit=False)
            new_food.save()

            for image_data in image_form.cleaned_data:
                if image_data:
                    image = image_data.get('image')
                    if image:
                        new_image = Image(food=new_food, image=image)
                        new_image.save()

            return render(request, self.template_name, {
                'categories': FoodCategory.objects.all(),
                'food_form': FoodForm(),
                'image_form': ImageFormSet(queryset=Image.objects.none()),
                'success': True,
            })

        return render(request, self.template_name, {
            'categories': FoodCategory.objects.all(),
            'food_form': food_form,
            'image_form': image_form,
        })


class FoodLogView(View):
    '''
    Allows the user to select food items and add them to their food log.
    Handles both GET and POST requests.
    '''

    def get(self, request):
        # Retrieve all food items and the food log of the logged-in user
        foods = Food.objects.all()
        user_food_log = FoodLog.objects.filter(user=request.user)

        # Render the food log page with the necessary context
        return render(request, 'food_log.html', {
            'categories': FoodCategory.objects.all(),
            'foods': foods,
            'user_food_log': user_food_log
        })

    def post(self, request):
        # Retrieve the food item selected by the user
        food_name = request.POST.get('food_consumed')
        if food_name:
            food_consumed = Food.objects.get(food_name=food_name)

            # Create and save a new food log entry for the logged-in user
            FoodLog.objects.create(user=request.user, food_consumed=food_consumed)

        # Redirect to the same page after saving the food log entry
        return redirect('food_log')


class FoodLogDeleteView(LoginRequiredMixin, View):
    '''
    This view allows the user to delete food items from their food log.
    '''

    def get(self, request, food_id):
        # Render the confirmation page with necessary context
        return render(request, 'food_log_delete.html', {
            'categories': FoodCategory.objects.all()
        })

    def post(self, request, food_id):
        # Get the food log item and delete it
        food_consumed = FoodLog.objects.filter(id=food_id)
        if food_consumed.exists():
            food_consumed.delete()
        return redirect('food_log')


@login_required
def weight_log_view(request):
    '''
    It allows the user to record their weight
    '''
    if request.method == 'POST':
        # get the values from the form
        weight = request.POST['weight']
        entry_date = request.POST['date']

        # get the currently logged in user
        user = request.user

        # add the data to the weight log
        weight_log = Weight(user=user, weight=weight, entry_date=entry_date)
        weight_log.save()

    # get the weight log of the logged in user
    user_weight_log = Weight.objects.filter(user=request.user)

    return render(request, 'user_profile.html', {
        'categories': FoodCategory.objects.all(),
        'user_weight_log': user_weight_log
    })


@login_required
def weight_log_delete(request, weight_id):
    '''
    It allows the user to delete a weight record from their weight log
    '''
    # get the weight log of the logged in user
    weight_recorded = Weight.objects.filter(id=weight_id)

    if request.method == 'POST':
        weight_recorded.delete()
        return redirect('weight_log')

    return render(request, 'weight_log_delete.html', {
        'categories': FoodCategory.objects.all()
    })


def categories_view(request):
    '''
    It renders a list of all food categories
    '''
    return render(request, 'categories.html', {
        'categories': FoodCategory.objects.all()
    })


def category_details_view(request, category_name):
    '''
    Clicking on the name of any category takes the user to a page that
    displays all of the foods in that category
    Food items are paginated: 4 per page
    '''
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse('login'))

    category = FoodCategory.objects.get(category_name=category_name)
    foods = Food.objects.filter(category=category)

    for food in foods:
        food.image = food.get_images.first()

    # Show 4 food items per page
    page = request.GET.get('page', 1)
    paginator = Paginator(foods, 4)
    try:
        pages = paginator.page(page)
    except PageNotAnInteger:
        pages = paginator.page(1)
    except EmptyPage:
        pages = paginator.page(paginator.num_pages)

    return render(request, 'food_category.html', {
        'categories': FoodCategory.objects.all(),
        'foods': foods,
        'foods_count': foods.count(),
        'pages': pages,
        'title': category.category_name
    })
