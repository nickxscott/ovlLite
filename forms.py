from datetime import datetime, date, timedelta

from flask_wtf import FlaskForm, Recaptcha, RecaptchaField
from wtforms import StringField, PasswordField, SubmitField, SelectField, BooleanField, IntegerField, DateField, TimeField
from wtforms.validators import InputRequired, Email, Length, EqualTo, NumberRange, ReadOnly
from wtforms_components import DateRange

from functions import createList, createSec, is_alphanumeric


class planForm(FlaskForm):
	date = DateField("date", validators=[InputRequired(message='Must enter a race date')
											#DateRange(min=date.today(), max=date.today() + timedelta(days=365))
											])
	dist = SelectField("distance", validators=[InputRequired(message='Must enter a race distance')],
						choices=[(3.1, '5k'), (6.2, '10k'), (13.1, 'Half-Marathon'), (26.2, 'Marathon')])
	weeks=SelectField("weeks", validators=[InputRequired()],
						choices=createList(8,16), default=12)
	pace_min=SelectField("pace_min", validators=[InputRequired(message='Must enter a pace')],
							choices=createList(3,12), default=8) 
	pace_sec = SelectField("pace_sec", validators=[InputRequired(message='Must enter a pace')],
							choices=createSec(0,59))
	units = SelectField("units", validators=[InputRequired(message='Must enter a distance unit')],
						choices=['mile', 'km'])
	name = StringField("name", validators=[InputRequired(), Length(max=50, message='Race names must be less than 50 characters'), is_alphanumeric], 
		render_kw={"placeholder": "Ex: NYC Marathon"})

class titleForm(FlaskForm):
	name = StringField("name", validators=[InputRequired(), Length(max=50, message='Race names must be less than 50 characters'), is_alphanumeric],
		render_kw={"placeholder": "Ex: NYC Marathon"})

class pwdResetForm(FlaskForm):
	email = StringField("email", validators=[InputRequired(),Email(	check_deliverability=True, message='Not a valid email address')],
						render_kw={"placeholder": "Email Address"})

class ResetPasswordForm(FlaskForm):
    password = PasswordField("New Password", validators=[InputRequired(message='Passwords must match')])
    password2 = PasswordField(
        "Repeat Password", validators=[InputRequired(message='Passwords must match'), EqualTo("password", message='Passwords must match')]
    )
    submit = SubmitField("Confirm Password Reset")

class settingsForm(FlaskForm):
	f_name = StringField("first", validators=[InputRequired(message='Must enter first name'),
							Length(max=20, message='First name must be less than 20 characters'), is_alphanumeric], render_kw={"placeholder": "First Name"})
	l_name = StringField("last", validators=[InputRequired(message='Must enter last name'),
						Length(max=20, message='Last name must be less than 20 characters'), is_alphanumeric], render_kw={"placeholder": "Last Name"})
	email = StringField("email", validators=[InputRequired(),Email(	check_deliverability=True, message='Not a valid email address')],
						render_kw={"placeholder": "Email Address"}) 
	email_pref=SelectField("email_pref", validators=[InputRequired()],
						choices=['Weekly', 'Daily', 'Never'])
	
class inquiryForm(FlaskForm):
	level = SelectField("level", validators=[InputRequired()],
						choices=['Beginner', 'Intermediate', 'Advanced'])

class lookupForm(FlaskForm):
	email = StringField("email", validators=[InputRequired()], render_kw={"placeholder": "Enter User Email"})