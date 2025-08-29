from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import PromptForm, CategoryForm
from .models import Prompt, Category
from django.db.models import Q


def is_superuser(user):
    return user.is_authenticated and user.is_superuser


@login_required
def prompt_list(request):
    category_slug = request.GET.get("kategorie")
    show_mine = request.GET.get("meine") == "1"

    prompts = Prompt.objects.all()

    if show_mine:
        prompts = prompts.filter(owner=request.user)
    else:
        # Zeige öffentliche Prompts + eigene private
        prompts = prompts.filter(Q(visibility="public") | Q(owner=request.user))

    selected_category = None
    if category_slug:
        selected_category = get_object_or_404(Category, slug=category_slug)
        prompts = prompts.filter(category=selected_category)

    categories = Category.objects.all().order_by("name")

    return render(
        request,
        "promptpro/prompt_list.html",
        {
            "prompts": prompts.select_related("category", "owner"),
            "categories": categories,
            "selected_category": selected_category,
            "show_mine": show_mine,
        },
    )


@login_required
def prompt_create(request):
    if request.method == "POST":
        form = PromptForm(request.POST)
        if form.is_valid():
            prompt = form.save(commit=False)
            prompt.owner = request.user
            prompt.save()
            messages.success(request, "Prompt gespeichert.")
            return redirect("promptpro:prompt_list")
    else:
        form = PromptForm()
    return render(request, "promptpro/prompt_form.html", {"form": form, "title": "Neuer Prompt"})


@login_required
def prompt_edit(request, pk):
    prompt = get_object_or_404(Prompt, pk=pk)
    if prompt.owner != request.user and not request.user.is_superuser:
        messages.error(request, "Du darfst diesen Prompt nicht bearbeiten.")
        return redirect("promptpro:prompt_list")

    if request.method == "POST":
        form = PromptForm(request.POST, instance=prompt)
        if form.is_valid():
            form.save()
            messages.success(request, "Prompt aktualisiert.")
            return redirect("promptpro:prompt_list")
    else:
        form = PromptForm(instance=prompt)
    return render(request, "promptpro/prompt_form.html", {"form": form, "title": "Prompt bearbeiten"})


@login_required
def prompt_delete(request, pk):
    prompt = get_object_or_404(Prompt, pk=pk)
    if prompt.owner != request.user and not request.user.is_superuser:
        messages.error(request, "Du darfst diesen Prompt nicht löschen.")
        return redirect("promptpro:prompt_list")
    if request.method == "POST":
        prompt.delete()
        messages.success(request, "Prompt gelöscht.")
        return redirect("promptpro:prompt_list")
    return render(request, "promptpro/prompt_confirm_delete.html", {"prompt": prompt})


@login_required
def category_overview(request):
    categories = Category.objects.all().order_by("name").prefetch_related("prompts")
    return render(request, "promptpro/category_overview.html", {"categories": categories})


@login_required
@user_passes_test(is_superuser)
def category_list(request):
    categories = Category.objects.all().order_by("name")
    return render(request, "promptpro/category_list.html", {"categories": categories})


@login_required
@user_passes_test(is_superuser)
def category_create(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Kategorie erstellt.")
            return redirect("promptpro:category_list")
    else:
        form = CategoryForm()
    return render(request, "promptpro/category_form.html", {"form": form, "title": "Neue Kategorie"})


@login_required
@user_passes_test(is_superuser)
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Kategorie aktualisiert.")
            return redirect("promptpro:category_list")
    else:
        form = CategoryForm(instance=category)
    return render(request, "promptpro/category_form.html", {"form": form, "title": "Kategorie bearbeiten"})


@login_required
@user_passes_test(is_superuser)
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        category.delete()
        messages.success(request, "Kategorie gelöscht.")
        return redirect("promptpro:category_list")
    return render(request, "promptpro/category_confirm_delete.html", {"category": category})
