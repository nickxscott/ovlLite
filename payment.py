#flask imports
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, session
from flask_login import login_required, logout_user, current_user


#custom imports
from ..forms import *
from ..functions import *
from ..user import User

#strip imports
import stripe
stripe.api_key = stripe_secret_key

#python imports
import calendar


payment_bp = Blueprint('payment', __name__, template_folder='../templates')

@login_manager.user_loader
def load_user(id):
	return User.get(id)

@payment_bp.route('/create', methods=['GET','POST'])
@login_required
def create():
	form = planForm()
	df_plans=get_plans(user_id=current_user.id)
	today=date.today()
	if request.method=='GET':

		return render_template('/payment/create.html', form=form)

	elif request.method=='POST' and form.validate_on_submit():

		race_name=form.name.data

		race_date=form.date.data
		weeks=int(form.weeks.data)
		#get race speed depending on units (km vs miles)
		m=int(form.pace_min.data)
		s=int(form.pace_sec.data)

		if form.units.data=='km':
			speed=minskm_to_meters(m=m, s=s)
		else:
			speed=mins_to_meters(m=m, s=s)

		race_dist=float(form.dist.data)
		units=form.units.data
		
		result=get_calendar(date=race_date, weeks=weeks, speed=speed, race_dist=race_dist, units=units)
		#CHECK PLAN BEFORE INSERT
		#rule 1 - not too fast. cannot exceed level 11.1
		if result[1] > 11.1:
			flash('You\'re too fast for us! Try a slower plan, or you may require a professional coach. Good luck!')
			return render_template('/payment/create.html', form=form, error=True)
		else:
			pass			
		#rule 2 - not too slow. cannot be less than level 1.1
		if result[1] < 1.1:
			flash('We\'re sorry, but we cannot create a plan for that pace. Try a beginner plan, or seek a coach to acheive your goals. Good luck!')
			return render_template('/payment/create.html', form=form, error=True)
		else:
			pass
		#rule 3 - make sure plan start isn't before today
		if result[0].date.min()<date.today():
			flash('This plan will start prior to today. Choose a plan with fewer weeks, or choose a later race.')
			return render_template('/payment/create.html', form=form, error=True)
		else:
			pass
		#rule 4 - make sure race date is less than a year away
		if result[0].date.max()> date.today() + timedelta(days=365):
			flash('Your race date cannot be more than a year away.')
			return render_template('/payment/create.html', form=form, error=True)
		else:
			pass
		#rule 5 - plan cannot overlap existing plan
		#create dictionary of plan_id:race_dates as list
		d_list={}
		for index, row in df_plans.iterrows():
			delta=row.race_date-row.start_date
			date_list = [(row.race_date + timedelta(days=1)) - timedelta(days=x) for x in range(1,(delta.days+1))]
			d_list[row.plan_id]=date_list
		#iterrate through dictionary and current race dates to find any common dates
		start_date = result[0].date.min()
		end_date = result[0].date.max()
		delta=end_date-start_date
		new_race_dates = [(end_date + timedelta(days=1)) - timedelta(days=x) for x in range(1,(delta.days+1))]
		for keys, values in d_list.items():
			for d in new_race_dates:
				if d in values:
					flash('You currently have a plan that overlaps this one. You can only have one plan at any given time. Choose a plan that does not overlap.')
					return render_template('/payment/create.html', form=form, error=True)
					break
				else:
					continue
		##escape special characters from subj and body
		racename_escaped=race_name.replace('"', '\\"')
		racename_escaped=race_name.replace('\'', '\\\'')

		#store form input in temp table while user is redirected to stripe
		plan_temp(	user_id=current_user.id, 
					race_name=racename_escaped, 
					race_date=race_date, 
					dist=race_dist, 
					weeks=weeks, 
					speed=speed, 
					units=units)

		################################################
		### REMOVING PAYMENT STEP FOR NOW 02-02-2025 ###
		################################################
		#return redirect(url_for('payment.create_checkout_session'))
		return redirect(url_for('payment.success'))
	else:
		for fieldName, errorMessages in form.errors.items():
			for err in errorMessages:
				flash(err )
		return render_template('/payment/create.html', form=form, error=True)

@payment_bp.route('/race_date/<rd>/<weeks>',methods=['GET','POST'])
@login_required
def race_date(rd, weeks):
	d=datetime.strptime(rd, '%Y-%m-%d')
	wks=int(weeks)
	plan_start=get_start_date(date=d, weeks=wks)
	return jsonify({'plan_start': plan_start})

@payment_bp.route("/create-checkout-session", methods=['GET', 'POST'])
@login_required
def create_checkout_session():
	domain_url = domain
	#stripe.api_key = stripe_secret_key

	try:
		# Create new Checkout Session for the order
		# Other optional params include:
		# [billing_address_collection] - to display billing address details on the page
		# [customer] - if you have an existing Stripe Customer ID
		# [payment_intent_data] - capture the payment later
		#[customer_email] - prefill the email input in the form
		# For full details see https://stripe.com/docs/api/checkout/sessions/create

		# ?session_id={CHECKOUT_SESSION_ID} means the redirect will have the session ID set as a query param

		#get item id
		df_temp=get_plan_temp(user_id=current_user.id)
		weeks=df_temp.weeks.values[0]
		df_price=get_plan_price(weeks=weeks, instance=instance)
		price=df_price.price_id.values[0]

		checkout_session = stripe.checkout.Session.create(
			client_reference_id=current_user.id if current_user.is_authenticated else None,
			success_url=domain_url + "success?session_id={CHECKOUT_SESSION_ID}",
			cancel_url=domain_url + "cancelled",
			payment_method_types=["card"],
			mode="payment",
			customer_email=current_user.email.lower(),
			allow_promotion_codes=True,
			#retrieve product from db based on weeks parameter
			line_items=[{'price': price, 
						'quantity': 1}]
			)	
		
		return redirect(checkout_session.url)
	except Exception as e:
		return jsonify(error=str(e)), 403

@payment_bp.route('/invoice/<user_id>',methods=['GET'])
@login_required
def invoice(user_id):
	#step 1 - see if customer exists. if not, create customer
	try:
		df_customer=get_sql(query='sql/searchCustomer.sql', user_id=user_id, env=instance.lower())
		customer_id=df_customer.customer_id.values[0]
		print('found customer! id: ', customer_id)
	except:
		df_user=get_sql(query='sql/getUserFromID.sql', user_id=user_id)
		name=df_user.first_name.values[0]+' '+df_user.last_name.values[0]
		email=df_user.email.values[0]
		customer = stripe.Customer.create(name=name,
										  email=email)
		customer_id=customer['id']
		print('creating new customer! id: ', customer_id)
		get_sql(query='sql/createCustomer.sql', user_id=user_id, customer_id=customer_id, env=instance.lower(),no_return=True)

	#step 2 - create invoice
	invoice = stripe.Invoice.create(customer=customer_id,
									collection_method="send_invoice",
									days_until_due=30)
	print('created invoice. invoice id: ', invoice['id'])
	#step 3 - add "item" to invoice (coaching fee price)
	invoice_item = stripe.InvoiceItem.create( 	customer=customer_id,
  												pricing={"price": price},
  												invoice=invoice['id'])
	#step 4 - send invoice
	invoice_sent=stripe.Invoice.send_invoice(invoice['id'])

	print('invoice sent!')

	return redirect(url_for('coaching.dashboard', user_id=user_id))

@payment_bp.route("/webhook", methods=["POST"])
def stripe_webhook():
	payload = request.get_data(as_text=True)
	sig_header = request.headers.get("Stripe-Signature")

	try:
		event = stripe.Webhook.construct_event(
			payload, sig_header, stripe_endpoint_secret
		)

	except ValueError as e:
		# Invalid payload
		return "Invalid payload", 400
	except stripe.error.SignatureVerificationError as e:
		# Invalid signature
		return "Invalid signature", 400

	if event["type"] == "invoice.sent":
		ev_data=event['data']['object']

		#check to see if invoice already created
		try:
			df_invoice=get_sql(query='sql/checkInvoice.sql', invoice_id=ev_data['id'], env=instance.lower())
			print('invoice already exists. all good.')
		except:
			#insert invoice record 
			df_customer=get_sql(query='sql/searchCustomerID.sql', customer_id=ev_data['customer'], env=instance.lower())
			get_sql(query='sql/createInvoice.sql', 
					user_id=df_customer.user_id.values[0], 
					invoice_id=ev_data['id'],
					env=instance.lower(), 
					amount=ev_data['amount_due'],
					no_return=True)
			print('invoice record inserted!')

	if event["type"] == "invoice.paid":
		#iupdate invoice record to paid
		ev_data=event['data']['object']
		get_sql(query='sql/updateInvoice.sql', invoice_id=ev_data['id'], no_return=True)
		print('invoice record paid!')
		
	return "Success", 200


@payment_bp.route("/edit/<plan_id>", methods=['GET', 'POST'])
@login_required
def edit(plan_id):
	today=date.today()

	form = planForm()
	df=get_plan(plan_id)
	
	#make sure plan being edited belongs to current user
	if df.user_id.values[0]!=current_user.id:
		return render_template("error.html"),500
	#make sure plan being edited is in the future
	if df.start_date.values[0]<=today:
		return render_template("error.html"),500


	if request.method=='GET':

		diff=df.race_date.values[0] - df.start_date.values[0]
		weeks=round(diff.days / 7)

		mins, sec = meters_to_mins(df.speed.values[0])
		mins=round(mins)
		sec=round(sec)

		form.name.data=df.race_name.values[0]
		form.date.data=df.race_date.values[0]
		form.dist.data=str(df.dist.values[0])
		form.weeks.data=str(weeks)
		form.pace_min.data=str(mins)
		form.pace_sec.data=str(sec)
		form.units.data=df.units.values[0]

		return render_template('/payment/editPlan.html', form=form, plan_id=plan_id)

	if request.method=='POST':
		print('weeks: ', form.weeks.data)
		#get all active user plans to make sure no overlapping occurs
		df_plans=get_plans(user_id=current_user.id)
		#remove selected plan from df_plans
		df_plans=df_plans[df_plans.plan_id!=int(plan_id)]
				
		race_name=form.name.data
		race_date=form.date.data
		weeks=int(form.weeks.data)
		#get race speed depending on units (km vs miles)
		m=int(form.pace_min.data)
		s=int(form.pace_sec.data)
		if form.units.data=='km':
			speed=minskm_to_meters(m=m, s=s)
		else:
			speed=mins_to_meters(m=m, s=s)

		race_dist=float(form.dist.data)
		units=form.units.data
		result=get_calendar(date=race_date, weeks=weeks, speed=speed, race_dist=race_dist, units=units)
		#CHECK PLAN BEFORE INSERT
		#rule 1 - not too fast. cannot exceed level 11.1
		if result[1] > 11.1:
			flash('You\'re too fast for us! Try a slower plan, or you may require a professional coach. Good luck!')
			return render_template('/payment/editPlan.html', form=form, error=True)
		else:
			pass			
		#rule 2 - not too slow. cannot be less than level 1.1
		if result[1] < 1.1:
			flash('We\'re sorry, but we cannot create a plan for that pace. Try a beginner plan, or seek a coach to acheive your goals. Good luck!')
			return render_template('/payment/editPlan.html', form=form, error=True)
		else:
			pass
		#rule 3 - make sure plan start isn't before today
		if result[0].date.min()<date.today():
			flash('This plan will start prior to today. Choose a later race date.')
			return render_template('/payment/editPlan.html', form=form, error=True)
		else:
			pass
		#rule 4 - make sure race date is less than a year away
		if result[0].date.max()> date.today() + timedelta(days=365):
			flash('Your race date cannot be more than a year away.')
			return render_template('/payment/editPlan.html', form=form, error=True)
		else:
			pass
		#rule 5 - plan cannot overlap existing plan
		#create dictionary of plan_id:race_dates as list
		d_list={}
		for index, row in df_plans.iterrows():
			delta=row.race_date-row.start_date
			date_list = [(row.race_date + timedelta(days=1)) - timedelta(days=x) for x in range(1,(delta.days+1))]
			d_list[row.plan_id]=date_list
		#iterrate through dictionary and current race dates to find any common dates
		start_date = result[0].date.min()
		end_date = result[0].date.max()
		delta=end_date-start_date
		new_race_dates = [(end_date + timedelta(days=1)) - timedelta(days=x) for x in range(1,(delta.days+1))]
		for keys, values in d_list.items():
			for d in new_race_dates:
				if d in values:
					flash('You currently have a plan that overlaps this one. You can only have one plan at any given time. Choose a plan that does not overlap.')
					return render_template('/payment/editPlan.html', form=form, error=True)
					break
				else:
					continue
		##escape special characters from subj and body
		racename_escaped=race_name.replace('"', '\\"')
		racename_escaped=race_name.replace('\'', '\\\'')

		#mark original plan as edited in user_plans table

		edit_plan(plan_id)
		#insert plan into db
		plan_id = plan_insert(	user_id=current_user.id, 
								dist=race_dist,  
								race_name=racename_escaped, 
								units=form.units.data, 
								speed=speed,
								start_date=result[0].date.min(), 
								race_date=form.date.data,
								level=result[1],
								plan=result[0])
		return  redirect(url_for('dashboard.my_plans'))

@payment_bp.route("/cancel/<plan_id>", methods=['GET'])
@login_required
def cancel(plan_id):
	#make sure plan being cancelled belongs to current user
	df=get_plan(plan_id)
	if df.user_id.values[0]!=current_user.id:
		return render_template("error.html"),500
	cancel_plan(plan_id=plan_id)
	return  redirect(url_for('dashboard.my_plans'))

@payment_bp.route("/modify/<plan_id>", methods=['GET', 'POST'])
@login_required
def modify(plan_id):
	today=date.today()

	form = planForm()
	df=get_plan(plan_id)
	
	#make sure plan being edited belongs to current user
	if df.user_id.values[0]!=current_user.id:
		return render_template("error.html"),500

	if request.method=='GET':

		diff=df.race_date.values[0] - df.start_date.values[0]
		weeks=round(diff.days / 7)

		mins, sec = meters_to_mins(df.speed.values[0])
		mins=round(mins)
		sec=round(sec)

		form.name.data=df.race_name.values[0]
		form.date.data=df.race_date.values[0]
		form.dist.data=str(df.dist.values[0])
		form.weeks.data=str(weeks)
		form.weeks.choices=[x for x in range(8,weeks+1)]
		form.pace_min.data=str(mins)
		form.pace_sec.data=str(sec)
		form.units.data=df.units.values[0]

		return render_template('/payment/modifyPlan.html', plan_id=plan_id,form=form)

	if request.method=='POST':
		#get all active user plans to make sure no overlapping occurs
		df_plans=get_plans(user_id=current_user.id)
		#remove selected plan from df_plans
		df_plans=df_plans[df_plans.plan_id!=int(plan_id)]
				
		race_name=form.name.data
		race_date=df.race_date.values[0]
		weeks=int(form.weeks.data)
		#get race speed depending on units (km vs miles)
		m=int(form.pace_min.data)
		s=int(form.pace_sec.data)
		if form.units.data=='km':
			speed=minskm_to_meters(m=m, s=s)
		else:
			speed=mins_to_meters(m=m, s=s)

		race_dist=float(form.dist.data)
		units=form.units.data
		result=get_calendar(date=race_date, weeks=weeks, speed=speed, race_dist=race_dist, units=units)
		#CHECK PLAN BEFORE INSERT
		#rule 1 - not too fast. cannot exceed level 11.1
		if result[1] > 11.1:
			flash('You\'re too fast for us! Try a slower plan, or you may require a professional coach. Good luck!')
			return render_template('/payment/modifyPlan.html', form=form, error=True)
		else:
			pass			
		#rule 2 - not too slow. cannot be less than level 1.1
		if result[1] < 1.1:
			flash('We\'re sorry, but we cannot create a plan for that pace. Try a beginner plan, or seek a coach to acheive your goals. Good luck!')
			return render_template('/payment/modifyPlan.html', form=form, error=True)
		else:
			pass
		### REMOVE RULE 3. START DATE CAN BE BEFORE TODAY WHEN MODIFYING PLAN ###
		#rule 3 - make sure plan start isn't before today
		#if result[0].date.min()<date.today():
		#	flash('This plan will start prior to today. Choose a later race date.')
		#	return render_template('/payment/modifyPlan.html', form=form, error=True)
		#else:
		#	pass
		#rule 4 - make sure race date is less than a year away
		if result[0].date.max()> date.today() + timedelta(days=365):
			flash('Your race date cannot be more than a year away.')
			return render_template('/payment/modifyPlan.html', form=form, error=True)
		else:
			pass
		#rule 5 - plan cannot overlap existing plan
		#create dictionary of plan_id:race_dates as list
		d_list={}
		for index, row in df_plans.iterrows():
			delta=row.race_date-row.start_date
			date_list = [(row.race_date + timedelta(days=1)) - timedelta(days=x) for x in range(1,(delta.days+1))]
			d_list[row.plan_id]=date_list
		#iterrate through dictionary and current race dates to find any common dates
		start_date = result[0].date.min()
		end_date = result[0].date.max()
		delta=end_date-start_date
		new_race_dates = [(end_date + timedelta(days=1)) - timedelta(days=x) for x in range(1,(delta.days+1))]
		for keys, values in d_list.items():
			for d in new_race_dates:
				if d in values:
					flash('You currently have a plan that overlaps this one. You can only have one plan at any given time. Choose a plan that does not overlap.')
					return render_template('/payment/editPlan.html', form=form, error=True)
					break
				else:
					continue
		##escape special characters from subj and body
		racename_escaped=race_name.replace('"', '\\"')
		racename_escaped=race_name.replace('\'', '\\\'')

		#mark original plan as edited in user_plans table
		edit_plan(plan_id)
		#insert plan into db
		plan_id = plan_insert(	user_id=current_user.id, 
								dist=race_dist,  
								race_name=racename_escaped, 
								units=form.units.data, 
								speed=speed,
								start_date=result[0].date.min(), 
								race_date=race_date,
								level=result[1],
								plan=result[0])
		return  redirect(url_for('dashboard.my_plans'))

@payment_bp.route("/success")
def success():

	#get most recent temp plan
	df=get_plan_temp(user_id=current_user.id)
	#get plan start date for printing
	d=df.race_date.values[0]
	wks=int(df.weeks.values[0])
	plan_start=get_start_date(date=d, weeks=wks)

	#rebuild plan and insert after successful payment
	result=get_calendar(date=df.race_date.values[0], 
						weeks=df.weeks.values[0], 
						speed=df.speed.values[0], 
						race_dist=df.dist.values[0], 
						units=df.units.values[0])

	#######################################
	### INSERT PLAN FOR FREE 02-02-2025 ###
	#######################################
	plan_id=plan_insert(user_id=current_user.id, 
						dist=df.dist.values[0],  
						race_name=df.race_name.values[0], 
						units=df.units.values[0], 
						speed=df.speed.values[0],
						start_date=result[0].date.min(), 
						race_date=df.race_date.values[0],
						level=result[1],
						plan=result[0])
	###########################################
	### END INSERT PLAN FOR FREE 02-02-2025 ###
	###########################################


	return render_template('/payment/planSubmit.html', start_date=plan_start, race_name=df.race_name.values[0])


@payment_bp.route("/cancelled")
def cancelled():
	return render_template("/payment/cancelled.html")