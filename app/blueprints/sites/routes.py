from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.blueprints.sites import sites_bp
from app.models.site import Site
from app.models.project import Project
from app.models.letter import Letter
from app.utils.access import admin_required, head_office_required

@sites_bp.route('/')
@login_required
@head_office_required
def list_sites():
    sites = Site.query.all()
    return render_template('sites.html', sites=sites)

@sites_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
@head_office_required
def create_site():
    if request.method == 'POST':
        name = request.form.get('name')
        code = request.form.get('code')
        description = request.form.get('description')
        address = request.form.get('address')
        
        # Validate required fields
        if not name or not code:
            flash('Site name and code are required', 'error')
            return redirect(url_for('sites.create_site'))
        
        # Check if site name or code already exists
        if Site.query.filter_by(name=name).first():
            flash('Site name already exists', 'error')
            return redirect(url_for('sites.create_site'))
            
        if Site.query.filter_by(code=code).first():
            flash('Site code already exists', 'error')
            return redirect(url_for('sites.create_site'))
        
        # Create site
        site = Site(
            name=name,
            code=code,
            description=description,
            address=address
        )
        
        db.session.add(site)
        db.session.commit()
        
        flash('Site created successfully', 'success')
        return redirect(url_for('sites.list_sites'))
    
    return render_template('create_site.html')

@sites_bp.route('/<int:site_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
@head_office_required
def edit_site(site_id):
    site = Site.query.get_or_404(site_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        code = request.form.get('code')
        description = request.form.get('description')
        address = request.form.get('address')
        
        # Validate required fields
        if not name or not code:
            flash('Site name and code are required', 'error')
            return redirect(url_for('sites.edit_site', site_id=site.id))
        
        # Check if updated name or code conflicts with existing sites
        name_exists = Site.query.filter(Site.name == name, Site.id != site.id).first()
        if name_exists:
            flash('Site name already exists', 'error')
            return redirect(url_for('sites.edit_site', site_id=site.id))
            
        code_exists = Site.query.filter(Site.code == code, Site.id != site.id).first()
        if code_exists:
            flash('Site code already exists', 'error')
            return redirect(url_for('sites.edit_site', site_id=site.id))
        
        # Update site
        site.name = name
        site.code = code
        site.description = description
        site.address = address
        
        db.session.commit()
        
        flash('Site updated successfully', 'success')
        return redirect(url_for('sites.list_sites'))
    
    return render_template('edit_site.html', site=site)

@sites_bp.route('/<int:site_id>/delete', methods=['POST'])
@login_required
@admin_required
@head_office_required
def delete_site(site_id):
    site = Site.query.get_or_404(site_id)
    
    # Check if site is in use
    if site.name == 'Head Office':
        flash('Cannot delete Head Office site', 'error')
        return redirect(url_for('sites.list_sites'))
    
    # Check if site has projects
    if Project.query.filter_by(site_id=site.id).count() > 0:
        flash('Cannot delete site with associated projects', 'error')
        return redirect(url_for('sites.list_sites'))
    
    # Check if site has users
    if site.users.count() > 0:
        flash('Cannot delete site with associated users', 'error')
        return redirect(url_for('sites.list_sites'))
    
    db.session.delete(site)
    db.session.commit()
    
    flash('Site deleted successfully', 'success')
    return redirect(url_for('sites.list_sites')) 