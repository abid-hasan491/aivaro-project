from app import app, db, User

with app.app_context():
    # পুরনো সব টেবিল মুছে ফেলা হচ্ছে
    db.drop_all()
    print("Old database deleted...")

    # নতুন টেবিল তৈরি করা হচ্ছে (sizes কলাম সহ)
    db.create_all()
    print("New database created successfully!")

    # নতুন অ্যাডমিন ইউজার তৈরি করা হচ্ছে
    if not User.query.filter_by(email='admin@zyrae.com').first():
        admin = User(name='Zyrae Admin', email='admin@zyrae.com', is_admin=True)
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("Admin account created: admin@zyrae.com / admin123")

print("✅ Setup Complete! You can now run 'python app.py'")