from django.contrib import admin

from .models import (
	Booking, BookingSeat, CastMember, Genre, Language, Movie, MovieCast,
	MovieImage, PaymentTransaction, Reservation, ReservationSeat, Review,
	ReviewReport, Seat, Show, Theater,
)


class MovieImageInline(admin.TabularInline):
	model = MovieImage
	extra = 1


class MovieCastInline(admin.TabularInline):
	model = MovieCast
	extra = 1


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
	list_display = ("title", "primary_language", "age_certification", "duration_minutes", "release_date", "average_rating")
	list_filter = ("primary_language", "genres", "age_certification")
	search_fields = ("title", "description", "cast_members__cast_member__name")
	filter_horizontal = ("genres",)
	inlines = (MovieImageInline, MovieCastInline)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
	list_display = ("movie", "user", "rating", "is_verified_viewer", "is_published", "created_at")
	list_filter = ("is_published", "is_verified_viewer", "rating")
	search_fields = ("movie__title", "user__username", "body")


@admin.register(Show)
class ShowAdmin(admin.ModelAdmin):
	list_display = ("movie", "theater", "starts_at", "ticket_price")
	list_filter = ("theater", "movie")
	date_hierarchy = "starts_at"


admin.site.register([Seat, Reservation, ReservationSeat, Theater, Booking, BookingSeat, PaymentTransaction, CastMember, Genre, Language, ReviewReport])
