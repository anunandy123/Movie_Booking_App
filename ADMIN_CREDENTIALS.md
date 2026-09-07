# Admin Access Report

The application uses Django's `is_staff` authorization for the business dashboard. No administrator password is committed to this repository.

Create and share the deployment credentials through the hosting provider's secret manager:

```bash
python manage.py createsuperuser
```

After login, authorized staff can use `/admin-dashboard/` and `/admin-dashboard/report.csv`.