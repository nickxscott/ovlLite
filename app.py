
#imports
from flask import Flask, url_for, render_template, request, jsonify
from flask_login import LoginManager, login_required
from flask_bcrypt import Bcrypt
from cryptography.fernet import Fernet

#python imports
import json
import string

#custom functions
from functions import *
from forms import *


#create app object
app = Flask(__name__, static_url_path='/static')
sk = ''.join(random.choices(string.ascii_uppercase +string.ascii_lowercase+string.digits, k=60))
app.secret_key = sk


@app.route('/',methods=['GET','POST']) 
def home():
	form=planForm()
	plan=False
	if request.method=='POST':
		plan=True
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
		
		result=get_calendar_hardcore(date=race_date, weeks=weeks, speed=speed, race_dist=race_dist, units=units)
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

		planBar=overview_bar(df=result[0], units=units)
		if units=='km':
			cols=['date', 'day_desc', 'week', 'phase', 'dist_km', 'pace', 'run_name', 'run_desc']
		else:
			cols=['date', 'day_desc', 'week', 'phase', 'distance', 'pace', 'run_name', 'run_desc']
		display_names={	'date':'Date', 
						'day_desc': 'Day', 
						'week':'Week', 
						'phase':'Phase', 
						'distance':'Distance', 
						'dist_km':'Distance',
						'pace':'Pace', 
						'run_name':'Run Name', 
						'run_desc':'Description'}
		return render_template("create.html", 
								form=form,
								planBarJSON=planBar,
								plan=plan,
								df=result[0][cols].rename(columns=display_names))
	return render_template("create.html", 
							form=form,
							plan=plan)

@app.route('/race_date/<rd>/<weeks>',methods=['GET','POST'])
def race_date(rd, weeks):
	d=datetime.strptime(rd, '%Y-%m-%d')
	wks=int(weeks)
	plan_start=get_start_date(date=d, weeks=wks)
	return jsonify({'plan_start': plan_start})


@app.route('/guide', methods=['GET','POST'])
def guide():
	return render_template('workoutGuide.html')

@app.errorhandler(404)
def page_not_found(e):
	return render_template("error.html"),404


@app.errorhandler(500)
def server_error(e):
	return render_template("error.html"),500

if __name__ == '__main__':
	app.run(debug=True)