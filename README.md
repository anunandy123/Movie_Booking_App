# 🎬 Movie Management & Smart Ticket Booking System

A comprehensive **Django-based movie ticket booking platform** that provides movie discovery, secure seat reservation, online payments, automated ticket generation, reviews and ratings, personalized recommendations, and a real-time administrative analytics dashboard.

The system is designed to provide a complete end-to-end cinema booking experience for both **customers and administrators**.

---

## 📌 Project Overview

The Movie Management & Smart Ticket Booking System enables users to:

* Discover movies
* Search and filter movies
* View movie details and trailers
* Check theater and show schedules
* Select seats with live availability
* Temporarily reserve seats
* Make secure online payments
* Receive digital PDF tickets
* Download previous tickets
* Rate and review movies after watching them
* Report inappropriate reviews
* Receive personalized movie recommendations

Administrators can manage:

* Movies
* Genres
* Languages
* Cast members
* Posters
* Trailers
* Age certifications
* Theaters
* Screens
* Seats
* Show schedules
* Bookings
* Payments
* Reviews
* Users
* Reports
* Business analytics

---

# 🚀 Major Features

## 1. 🎥 Movie Management

Administrators can manage complete movie information through the Django Admin panel or a custom administration interface.

### Movie Information

Each movie supports:

* Movie title
* Description
* Genre
* Language
* Release date
* Duration
* Age certification
* Cast members
* Multiple poster images
* YouTube trailer
* Movie status
* Average rating
* View/popularity information

### Secure YouTube Trailer

Trailers are embedded securely using YouTube embed URLs rather than allowing arbitrary external content.

Example:

```text
https://www.youtube.com/embed/VIDEO_ID
```

---

# ⭐ 2. Reviews & Ratings

Registered users can submit reviews and ratings only if they have:

1. Booked the movie
2. Successfully completed the booking
3. Watched the movie

### Review Features

* 1–5 star ratings
* Written reviews
* Verified viewer badge
* Review editing
* Review reporting
* Inappropriate content reporting
* Average movie rating calculation
* Review timestamps

### Verified Viewer

Users who have successfully booked and watched a movie are marked as:

```text
✓ Verified Viewer
```

This helps improve the authenticity of reviews.

---

# 💺 3. Smart Seat Reservation

The application provides real-time seat availability while users select seats.

### Seat States

Each seat can have one of three states:

```text
🟢 Available
🟡 Temporarily Reserved
🔴 Booked
```

### Temporary Reservation

Selected seats are temporarily locked for **2 minutes**.

If payment is not completed within the reservation period:

```text
Reserved → Automatically Released → Available
```

### Concurrent Booking Protection

The system uses Django database transactions and row-level locking to prevent multiple users from booking the same seat simultaneously.

Important mechanisms include:

* `transaction.atomic()`
* `select_for_update()`
* Database constraints
* Reservation expiration timestamps
* Server-side validation

Example conceptual flow:

```text
User A ──┐
         ├──> Database Lock ──> Seat
User B ──┘

Only one request can successfully reserve the seat.
```

---

# 💳 4. Complete Payment Workflow

The application currently implements Stripe online payments. The payment provider is isolated in the transaction service so another provider can be added without changing booking confirmation rules.

The payment workflow handles:

* Successful payments
* Failed payments
* Cancelled payments
* Payment retries
* Webhook verification
* Duplicate payment prevention
* Transaction tracking

### Booking Confirmation Flow

```text
Select Seats
     ↓
Temporary Reservation
     ↓
Create Payment
     ↓
Payment Gateway
     ↓
Server-side Verification
     ↓
Payment Successful?
   ↙          ↘
 YES          NO
 ↓             ↓
Confirm       Release
Booking       Seats
 ↓
Generate Ticket
 ↓
Send Email
```

### Payment Security

Payment confirmation is performed on the server.

The system does **not** trust client-side payment status.

Every transaction stores:

* Transaction ID
* Booking ID
* Payment gateway
* Payment amount
* Payment status
* Payment timestamp
* Verification status

Duplicate payment confirmations cannot create duplicate bookings.

---

# 🎫 5. Automated Ticket Generation

After successful payment, the system automatically generates a professional PDF ticket.

The ticket contains:

* Movie name
* Movie poster
* Theater
* Screen
* Show date
* Show time
* Booked seats
* Booking ID
* Payment reference
* Ticket price
* QR code

Example:

```text
┌─────────────────────────────────────┐
│          MOVIE TICKET               │
├─────────────────────────────────────┤
│ Movie: Example Movie                │
│ Theater: ABC Cinemas                │
│ Screen: Screen 2                    │
│ Date: 14 September 2026             │
│ Time: 07:30 PM                      │
│ Seats: A5, A6                       │
│ Booking ID: BK10234                 │
│ Payment ID: PAY78231                │
│                                     │
│             [ QR CODE ]             │
└─────────────────────────────────────┘
```

---

# 📧 6. Automated Email Confirmation

Ticket delivery is handled asynchronously using **Celery**.

The booking process does not wait for email delivery.

### Workflow

```text
Successful Payment
       ↓
Booking Confirmed
       ↓
Ticket Generated
       ↓
Celery Task
       ↓
Send Email
       ↓
Email Delivered
```

If email delivery fails:

```text
Email Failed
     ↓
Celery Retry
     ↓
Retry Attempt
     ↓
Successful Delivery
```

This ensures that email problems do not block the booking process.

---

# 🔎 7. Movie Discovery

Users can search and discover movies using multiple filters.

### Search

Users can search by:

* Movie title

### Filters

Movies can be filtered by:

* Genre
* Language
* City
* Theater
* Release date
* Rating
* Show timing

### Sorting

Results can be sorted by:

* Popularity
* Newest releases
* Rating
* Ticket price

### Additional Features

* Dynamic result count
* Pagination
* Optimized database queries
* Recommended movies

Example:

```text
Search: Avengers

Genre: Action
Language: English
Rating: 4+
City: Kolkata
Date: This Week

Results: 18 Movies
```

---

# 🤖 8. Personalized Recommendations

The system provides a:

## Recommended for You

section based on:

* Previous bookings
* Recently viewed movies
* Favorite genres
* Preferred languages
* Movie popularity
* Similar movies

Recommendation logic can consider:

```text
Booking History
       +
Recently Viewed Movies
       +
Genre Preference
       +
Language Preference
       ↓
Recommended Movies
```

---

# 🎞️ 9. Similar, Trending & Recently Released Movies

The movie details page displays additional movie recommendations.

### Similar Movies

Based on:

* Genre
* Language

### Trending Movies

Based on:

* Recent bookings
* View count
* Booking frequency
* Rating/popularity

### Recently Released

Based on:

* Release date

Example:

```text
Movie Details
     │
     ├── Similar Movies
     ├── Trending Movies
     └── Recently Released
```

---

# 📊 10. Admin Dashboard

The system includes a comprehensive administrative dashboard for monitoring business performance.

### Dashboard Metrics

Administrators can view:

* Total revenue
* Daily revenue
* Weekly revenue
* Monthly revenue
* Yearly revenue
* Booking trends
* Theater occupancy
* Most booked movies
* Top-performing theaters
* Peak booking hours
* Cancellation statistics
* Refund statistics
* User growth

---

# 📅 Custom Date Filtering

Administrators can select custom date ranges.

Example:

```text
From: 01 September 2026
To:   14 September 2026
```

The dashboard dynamically calculates:

* Revenue
* Bookings
* Occupancy
* Cancellations
* Refunds
* User growth

---

# 📈 Business Analytics

Example dashboard:

```text
┌───────────────────────────────────────────┐
│              ADMIN DASHBOARD              │
├───────────────────────────────────────────┤
│ Revenue              ₹1,25,450            │
│ Total Bookings       4,280                │
│ Occupancy             78.4%               │
│ Users                 8,921               │
├───────────────────────────────────────────┤
│              BOOKING TREND                │
│       ╱╲                                  │
│      ╱  ╲    ╱╲                          │
│  ╱╲ ╱    ╲  ╱  ╲                         │
│ ╱  ╲      ╲╱    ╲                        │
├───────────────────────────────────────────┤
│ Top Movie: Example Movie                 │
│ Top Theater: ABC Cinemas                 │
│ Peak Hour: 7 PM – 9 PM                   │
└───────────────────────────────────────────┘
```

---

# ⚡ 11. Database Optimization

The application is designed to efficiently handle at least:

```text
100,000+ bookings
```

Optimization techniques include:

* Database indexing
* `select_related()`
* `prefetch_related()`
* Django ORM aggregation
* `annotate()`
* `Count()`
* `Sum()`
* `Avg()`
* `F()`
* `Q()`
* Query filtering
* Pagination
* Database-level calculations

Example:

```python
Movie.objects.annotate(
    average_rating=Avg("reviews__rating")
)
```

Instead of loading thousands of records into Python memory, calculations are performed by the database.

---

# 🗄️ Database Indexing

Frequently queried fields should be indexed.

Example:

```python
class Booking(models.Model):
    created_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=20, db_index=True)
```

Composite indexes can also be used for frequently combined queries.

Example:

```python
class Meta:
    indexes = [
        models.Index(fields=["show", "status"]),
        models.Index(fields=["created_at", "status"]),
    ]
```

### Performance Improvement

Database optimization reduces:

* Query execution time
* Memory usage
* Number of database queries
* Response latency

and improves scalability for large datasets.

---

# 🔐 12. Authentication & Authorization

Django's authentication and permission system is used to protect administrative functionality.

### User Types

```text
Customer
   │
   ├── Browse Movies
   ├── Book Tickets
   ├── Make Payments
   ├── Review Movies
   └── View Booking History

Administrator
   │
   ├── Manage Movies
   ├── Manage Theaters
   ├── Manage Shows
   ├── Manage Bookings
   ├── Manage Users
   └── View Analytics
```

Only authorized administrators can access the admin dashboard.

---

# 🛡️ Security Features

The application follows secure server-side practices.

Implemented/proposed security mechanisms include:

* Django authentication
* Django authorization
* CSRF protection
* Server-side payment verification
* Payment webhook verification
* Database transactions
* Row-level locking
* Duplicate booking protection
* Duplicate payment protection
* Secure trailer embedding
* Input validation
* Permission-based admin access
* Environment variables for secrets

Sensitive credentials should never be committed to Git.

---

# 🏗️ Suggested Project Architecture

```text
movie-booking-system/
│
├── manage.py
│
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── accounts/
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   └── forms.py
│
├── movies/
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   └── services.py
│
├── theaters/
│   ├── models.py
│   ├── views.py
│   └── admin.py
│
├── bookings/
│   ├── models.py
│   ├── views.py
│   ├── services.py
│   └── tasks.py
│
├── payments/
│   ├── models.py
│   ├── views.py
│   ├── services.py
│   └── webhooks.py
│
├── reviews/
│   ├── models.py
│   ├── views.py
│   └── forms.py
│
├── recommendations/
│   ├── services.py
│   └── views.py
│
├── dashboard/
│   ├── views.py
│   ├── services.py
│   └── reports.py
│
├── templates/
│
├── static/
│
├── media/
│
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```

---

# 🔄 Complete Booking Lifecycle

```text
User
 │
 ▼
Browse Movies
 │
 ▼
Select Movie
 │
 ▼
Select Theater
 │
 ▼
Select Show
 │
 ▼
View Live Seat Availability
 │
 ▼
Select Multiple Seats
 │
 ▼
Temporary 2-Minute Reservation
 │
 ▼
Payment Gateway
 │
 ├───────────────┐
 │               │
 ▼               ▼
Success         Failure
 │               │
 ▼               ▼
Verify         Release Seats
Payment
 │
 ▼
Confirm Booking
 │
 ▼
Generate PDF Ticket
 │
 ▼
Generate QR Code
 │
 ▼
Celery Email Task
 │
 ▼
Email Ticket
 │
 ▼
Watch Movie
 │
 ▼
Submit Review & Rating
```

---

# 🧩 Core Technologies

| Technology          | Purpose               |
| ------------------- | --------------------- |
| Python              | Backend programming   |
| Django              | Web framework         |
| Django ORM          | Database operations   |
| HTML5               | Frontend structure    |
| CSS3                | Styling               |
| JavaScript          | Dynamic UI            |
| PostgreSQL / SQLite | Database              |
| Celery              | Background processing |
| Redis               | Celery broker/cache   |
| Stripe              | Online payments       |
| QR Code             | Ticket verification   |
| ReportLab           | PDF ticket generation |
| Django Admin        | Administration        |
| Git/GitHub          | Version control       |

---

# 📦 Installation

## 1. Clone the Repository

```bash
git clone <your-github-repository-url>
cd movie-booking-system
```

---

## 2. Create Virtual Environment

### Windows

```bash
python -m venv venv
```

Activate:

```bash
venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

---

# 📥 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

# ⚙️ 4. Configure Environment Variables

Create a `.env` file:

```env
SECRET_KEY=your-secret-key

DEBUG=True

DATABASE_URL=your-database-url

STRIPE_PUBLISHABLE_KEY=your-publishable-key
STRIPE_SECRET_KEY=your-secret-key
STRIPE_WEBHOOK_SECRET=your-webhook-secret

EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email
EMAIL_HOST_PASSWORD=your-email-password

CELERY_BROKER_URL=redis://localhost:6379/0
```

> Never upload `.env` to GitHub.

---

# 🗃️ 5. Run Database Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

---

# 👤 6. Create Django Admin Account

```bash
python manage.py createsuperuser
```

Enter:

```text
Username:
Email:
Password:
```

The admin panel can then be accessed through:

```text
/admin/
```

**Do not publish administrator credentials inside this README or Git repository.**

For the project submission/report, provide the administrator credentials through the required secure report/document.

---

# ▶️ 7. Start Django Server

```bash
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

Admin:

```text
http://127.0.0.1:8000/admin/
```

---

# 🔴 8. Start Redis

Celery requires Redis as the message broker.

Example:

```bash
redis-server
```

---

# 🟢 9. Start Celery Worker

Open another terminal:

```bash
celery -A config worker -l info
```

On Windows, if required:

```bash
celery -A config worker -l info --pool=solo
```

---

# 🧪 Testing

Run Django tests:

```bash
python manage.py test
```

Recommended test cases include:

### Movie

* Movie creation
* Movie update
* Movie deletion
* Trailer validation
* Poster upload
* Genre filtering

### Seat Reservation

* Multiple seat selection
* 2-minute reservation expiry
* Concurrent reservation
* Duplicate booking prevention
* Seat release after payment failure

### Payments

* Successful payment
* Failed payment
* Cancelled payment
* Payment retry
* Invalid webhook
* Duplicate webhook
* Duplicate payment confirmation

### Reviews

* Verified viewer validation
* Review creation
* Review editing
* Review reporting
* Rating calculation

### Tickets

* PDF generation
* QR code generation
* Email delivery
* Email retry

---

# 📊 Performance Testing

The application should be tested with large datasets, particularly:

```text
100,000+ bookings
```

Performance should be evaluated using:

```python
queryset.explain()
```

and Django Debug Toolbar during development.

Important metrics:

* Query count
* Query execution time
* Database response time
* API/page response time
* Memory usage
* Concurrent booking behavior

---

# 📤 CSV Report Export

Administrators can export analytics data as CSV.

Example reports:

```text
Revenue Report
Booking Report
Movie Performance Report
Theater Occupancy Report
Cancellation Report
Refund Report
User Growth Report
```

Example CSV:

```csv
Date,Movie,Theater,Bookings,Revenue
2026-09-01,Movie A,Theater 1,120,24000
2026-09-02,Movie B,Theater 2,95,19000
```

---
.

### Suggested Development Schedule

| Day   | Task                                              |
| ----- | ------------------------------------------------- |
| Day 1 | Movie, genre, language, cast & theater management |
| Day 2 | Show scheduling & smart seat reservation          |
| Day 3 | Payment gateway & booking workflow                |
| Day 4 | Ticket PDF, QR code & Celery email                |
| Day 5 | Search, filtering & recommendations               |
| Day 6 | Admin dashboard, analytics & CSV reports          |
| Day 7 | Testing, optimization, security & deployment      |

---

# 🚀 Future Enhancements

Possible future improvements include:

* Mobile application
* Push notifications
* AI-based recommendations
* Multiple payment gateways
* Loyalty/reward system
* Coupon management
* Dynamic ticket pricing
* Facial/QR-based theater entry
* Real-time WebSocket seat updates
* Multi-city cinema management
* Advanced fraud detection
* AI-powered review moderation

---

# 👩‍💻 Project Goals

The primary goals of this project are to demonstrate practical implementation of:

* Django web development
* Relational database design
* Django ORM optimization
* Transaction management
* Concurrency control
* Payment integration
* Background task processing
* PDF generation
* Email automation
* Authentication & authorization
* Recommendation systems
* Data analytics
* Query optimization
* Scalable backend architecture

---

# 📄 Project Status

| Module                 | Status            |
| ---------------------- | ----------------- |
| Movie Management       | 🔄 In Development |
| Theater Management     | 🔄 In Development |
| Show Scheduling        | 🔄 In Development |
| Smart Seat Reservation | 🔄 In Development |
| Payment Workflow       | 🔄 In Development |
| Booking Management     | 🔄 In Development |
| Reviews & Ratings      | 🔄 In Development |
| Movie Discovery        | 🔄 In Development |
| Recommendations        | 🔄 In Development |
| PDF Ticket Generation  | 🔄 In Development |
| Email Automation       | 🔄 In Development |
| Admin Dashboard        | 🔄 In Development |
| Analytics              | 🔄 In Development |
| CSV Reports            | 🔄 In Development |
| Testing & Optimization | ⏳ Pending         |
| Deployment             | ⏳ Pending         |

---

# 📜 License

This project is developed for educational and academic purposes.

---

# 🙌 Acknowledgements

* Django Documentation
* PostgreSQL Documentation
* Celery Documentation
* Redis Documentation
* Stripe payment and webhook documentation
* ReportLab Documentation

---

## ⭐ Final Objective

The final application should provide a secure, scalable and user-friendly movie booking platform capable of handling the complete lifecycle:

**Movie → Discovery → Show → Seat Reservation → Payment → Booking → Ticket → Email → Movie → Verified Review**

while maintaining **database consistency, payment security, concurrency safety and optimized performance**.
