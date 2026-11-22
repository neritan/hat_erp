"""Ratings made before reviews had a type: with an order they rate that order, without one they are
the hotel's overall review of the distributor."""

import frappe


def execute():
	frappe.db.sql(
		"""update `tabHAT Distributor Rating`
		set review_type = if(ifnull(order_request, '') = '', 'Overall', 'Order')
		where ifnull(review_type, '') = ''"""
	)
