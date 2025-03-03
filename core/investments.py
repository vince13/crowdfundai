def get_investment_context(app, user):
    """Get context data for investment view."""
    try:
        # Get basic app info
        share_price = app.share_price
        available_shares = app.get_available_shares()
        
        return {
            'app': app,
            'share_price': share_price,
            'available_shares': available_shares,
            'currency': 'NGN',
            'currency_symbol': '₦'
        }
    except Exception as e:
        logger.error(f"Error getting investment context: {e}")
        return {
            'error': str(e)
        } 