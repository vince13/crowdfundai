import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crowdfund_ai.settings')
django.setup()

from core.models import LegalDocument
from django.utils import timezone

def create_terms_of_service():
    tos_content = """
<h2>1. Acceptance of Terms</h2>
<p>By accessing and using CrowdFund AI ("the Platform"), you agree to be bound by these Terms of Service and all applicable laws and regulations.</p>

<h2>2. Platform Description</h2>
<p>CrowdFund AI is a marketplace connecting AI application developers with potential investors. The platform facilitates investment in AI applications through share ownership and revenue distribution.</p>

<h2>3. User Accounts</h2>
<p>Users must register for an account and maintain accurate, complete, and up-to-date account information. Users are responsible for maintaining the security of their account credentials.</p>

<h2>4. Developer Terms</h2>
<p>Developers listing AI applications on the platform must:</p>
<ul>
    <li>Own or have rights to the listed application</li>
    <li>Provide accurate information about the application</li>
    <li>Maintain the application and provide updates</li>
    <li>Honor revenue sharing agreements</li>
</ul>

<h2>5. Investor Terms</h2>
<p>Investors using the platform acknowledge:</p>
<ul>
    <li>Investment risks</li>
    <li>Share ownership terms</li>
    <li>Revenue distribution mechanisms</li>
    <li>Investment limitations</li>
</ul>

<h2>6. Revenue Distribution</h2>
<p>The platform facilitates revenue distribution according to share ownership percentages. All distributions are subject to platform fees and applicable taxes.</p>

<h2>7. Prohibited Activities</h2>
<p>Users agree not to:</p>
<ul>
    <li>Violate any laws or regulations</li>
    <li>Infringe on intellectual property rights</li>
    <li>Manipulate platform metrics</li>
    <li>Engage in fraudulent activities</li>
</ul>

<h2>8. Termination</h2>
<p>We reserve the right to terminate or suspend accounts for violations of these terms or for any other reason at our discretion.</p>

<h2>9. Disclaimers</h2>
<p>The platform is provided "as is" without warranties of any kind. We do not guarantee investment returns or application performance.</p>

<h2>10. Contact Information</h2>
<p>For questions about these terms, contact us at legal@crowdfundai.com</p>
"""

    LegalDocument.objects.create(
        document_type='TOS',
        version='1.0',
        content=tos_content,
        effective_date=timezone.now(),
        is_active=True
    )
    print("Terms of Service created successfully")

def create_privacy_policy():
    privacy_content = """
<h2>1. Information We Collect</h2>
<h3>Personal Information</h3>
<ul>
    <li>Name and contact information</li>
    <li>Account credentials</li>
    <li>Payment and banking information</li>
    <li>Government-issued identification (for KYC)</li>
</ul>

<h3>Usage Information</h3>
<ul>
    <li>Log data and device information</li>
    <li>Transaction history</li>
    <li>Platform interaction data</li>
    <li>Communication records</li>
</ul>

<h2>2. How We Use Your Information</h2>
<ul>
    <li>Process transactions and investments</li>
    <li>Verify identity and prevent fraud</li>
    <li>Provide customer support</li>
    <li>Send important updates and notifications</li>
    <li>Improve platform services</li>
</ul>

<h2>3. Information Sharing</h2>
<p>We share information with:</p>
<ul>
    <li>Payment processors and financial institutions</li>
    <li>Identity verification services</li>
    <li>Legal and regulatory authorities</li>
    <li>Service providers and partners</li>
</ul>

<h2>4. Data Security</h2>
<p>We implement appropriate security measures to protect your information, including:</p>
<ul>
    <li>Encryption of sensitive data</li>
    <li>Regular security assessments</li>
    <li>Access controls and monitoring</li>
    <li>Secure data storage</li>
</ul>

<h2>5. Your Rights</h2>
<p>You have the right to:</p>
<ul>
    <li>Access your personal information</li>
    <li>Correct inaccurate data</li>
    <li>Request data deletion</li>
    <li>Opt-out of marketing communications</li>
</ul>

<h2>6. Data Retention</h2>
<p>We retain your information for as long as necessary to:</p>
<ul>
    <li>Provide our services</li>
    <li>Comply with legal obligations</li>
    <li>Resolve disputes</li>
    <li>Enforce agreements</li>
</ul>

<h2>7. Cookies and Tracking</h2>
<p>We use cookies and similar technologies to:</p>
<ul>
    <li>Maintain session information</li>
    <li>Remember preferences</li>
    <li>Analyze platform usage</li>
    <li>Enhance security</li>
</ul>

<h2>8. Changes to Privacy Policy</h2>
<p>We may update this policy periodically. Users will be notified of significant changes.</p>

<h2>9. Contact Information</h2>
<p>For privacy-related inquiries, contact us at privacy@crowdfundai.com</p>
"""

    LegalDocument.objects.create(
        document_type='PRIVACY',
        version='1.0',
        content=privacy_content,
        effective_date=timezone.now(),
        is_active=True
    )
    print("Privacy Policy created successfully")

if __name__ == '__main__':
    create_terms_of_service()
    create_privacy_policy() 