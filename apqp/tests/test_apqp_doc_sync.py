# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase
from datetime import date

class TestAPQPDocSync(TransactionCase):
    
    def setUp(self):
        super(TestAPQPDocSync, self).setUp()
        
        # Create a product
        self.product = self.env['product.template'].create({
            'name': 'Test Product',
            'drg_no': 'DRG123',
        })
        
        # Create a customer
        self.partner = self.env['res.partner'].create({
            'name': 'Test Customer',
        })
        
        # Create a document package
        self.doc_package = self.env['xf.doc.approval.document.package'].create({
            'name': 'Original Project Name',
            'partner_id': self.partner.id,
            'part_id': self.product.id,
            'start_date': date(2026, 1, 1),
            'target_date': date(2026, 6, 1),
            'doc_type': 'safelaunch',
            'description': 'Original Description',
        })
        
        # Ensure timeline chart is created (it should be in create method of DocPackageInherit)
        self.timeline_chart = self.doc_package.apqp_timeline_chart_id
        
    def test_automatic_sync_on_write(self):
        """Test that updating doc package automatically updates timeline chart."""
        self.assertTrue(self.timeline_chart, "Timeline chart should be linked")
        self.assertEqual(self.timeline_chart.project_name, 'Original Project Name')
        
        # Update doc package
        self.doc_package.write({
            'name': 'Updated Project Name',
            'start_date': date(2026, 2, 1),
            'description': 'Updated Description',
        })
        
        # Verify timeline chart updated
        self.assertEqual(self.timeline_chart.project_name, 'Updated Project Name')
        self.assertEqual(self.timeline_chart.start_date, date(2026, 2, 1))
        self.assertEqual(self.timeline_chart.description, 'Updated Description')

    def test_manual_sync_method(self):
        """Test the manual refresh_data_from_package method."""
        # Manually change a value in doc package without write (unlikely in Odoo but for testing method)
        # Actually, let's just use write but check if the method works when called directly.
        
        self.doc_package.name = 'Manual Update Name'
        # Normally Odoo would trigger write here if using the setter, but let's assume we want to test the method robustness.
        self.timeline_chart.refresh_data_from_package()
        
        # Note: If .name = ... triggers write, then it's already synced. 
        # If not, refresh_data_from_package should pull it.
        self.assertEqual(self.timeline_chart.project_name, 'Manual Update Name')
