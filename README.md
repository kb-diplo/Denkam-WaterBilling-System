# Water Billing System

A comprehensive water billing system designed for efficient management of customer accounts, meter readings, and billing processes. It features a supplier-side dashboard for staff and a client-facing portal for customers.

## Features

### Supplier-Side Functionality (Admin & Staff)

*   **User Management:** Admins can create and manage staff accounts with different permission levels (e.g., Meter Readers).
*   **Customer Management:** Admins can add, edit, and view customer accounts.
*   **Meter Reading:** Authorized staff can submit new meter readings for customers.
*   **Billing Management:** The system tracks bills, payment status, and due dates.
*   **Reporting:** View lists of ongoing bills, paid bills, and manage user accounts.

### Customer Portal

*   **Account Dashboard:** Customers can view their current bills and full payment history.
*   **Usage Tracking:** Monitor water consumption over time.
*   **Document Access:** Download invoices and payment receipts (via PDF generation).
*   **Profile Management:** Customers can update their personal information.

## Technologies Used

*   **Backend:** Python, Django
*   **Frontend:** HTML, CSS, JavaScript, Bootstrap 5
*   **Database:** SQLite (development)
*   **Key Django Packages:**
    *   `django-crispy-forms` & `crispy-bootstrap5` for clean form rendering.
    *   `Pillow` for image processing.
    *   `sweetify` for user-friendly notifications.
    *   `xhtml2pdf` for generating PDF documents.
    *   `whitenoise` for serving static files in production.

## Installation

### Requirements

*   Python 3.9 or higher
*   `pip` package manager

### Setup Instructions

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/kb-diplo/Denkam-WaterBilling-System.git
    cd WaterBilling-master
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    # For Windows
    python -m venv venv
    venv\Scripts\activate

    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run database migrations:**
    ```bash
    python manage.py migrate
    ```

5.  **Create an admin superuser:**
    ```bash
    python manage.py createsuperuser
    ```

python manage.py collectstatic --noinput

6.  **Run the development server:**
    ```bash
    python manage.py runserver
    ```

## Project Structure

```
WaterBilling-master/
├── account/         # Handles user authentication, registration, and roles
├── core/            # Core project settings, WSGI configuration
├── main/            # Main application for billing, customer management, views
├── mpesa/           # M-Pesa payment integration logic
├── static/          # Static files (CSS, JS, images)
├── templates/       # HTML templates (within each app)
├── manage.py        # Django's command-line utility
└── requirements.txt # Project dependencies
```

## License

This project is licensed under the MIT License.

## Contact

Lawrence Mbugua - tingzlarry@gmail.com
