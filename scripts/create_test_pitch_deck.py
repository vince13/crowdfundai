from fpdf import FPDF

def create_test_pitch_deck():
    pdf = FPDF()
    
    # Title Page
    pdf.add_page()
    pdf.set_font("Arial", "B", 24)
    pdf.cell(0, 20, "AI-Powered Healthcare Assistant", align="C")
    pdf.ln(20)
    pdf.set_font("Arial", "", 16)
    pdf.cell(0, 10, "Revolutionizing Patient Care with Artificial Intelligence", align="C")
    
    # Problem Statement
    pdf.add_page()
    pdf.set_font("Arial", "B", 20)
    pdf.cell(0, 10, "Problem Statement", align="L")
    pdf.ln(15)
    pdf.set_font("Arial", "", 12)
    pdf.multi_cell(0, 10, "Healthcare providers face significant challenges in managing patient data, scheduling, and providing timely care. Current systems are fragmented, leading to inefficiencies and potential errors in patient care. Manual processes consume valuable time that could be better spent on direct patient care.")
    
    # Solution
    pdf.add_page()
    pdf.set_font("Arial", "B", 20)
    pdf.cell(0, 10, "Our Solution", align="L")
    pdf.ln(15)
    pdf.set_font("Arial", "", 12)
    pdf.multi_cell(0, 10, "We are developing an AI-powered healthcare assistant that streamlines administrative tasks, improves patient scheduling, and provides real-time insights for better decision-making. Our solution integrates with existing healthcare systems and uses advanced machine learning algorithms to optimize workflows.")
    
    # Market Analysis
    pdf.add_page()
    pdf.set_font("Arial", "B", 20)
    pdf.cell(0, 10, "Market Analysis", align="L")
    pdf.ln(15)
    pdf.set_font("Arial", "", 12)
    pdf.multi_cell(0, 10, "The global healthcare AI market is projected to reach $45 billion by 2026. Our initial target market includes small to medium-sized healthcare practices in North America, representing over 200,000 potential customers. We estimate our serviceable obtainable market (SOM) at $500 million.")
    
    # Team
    pdf.add_page()
    pdf.set_font("Arial", "B", 20)
    pdf.cell(0, 10, "Our Team", align="L")
    pdf.ln(15)
    pdf.set_font("Arial", "", 12)
    pdf.multi_cell(0, 10, "Our team combines expertise in healthcare, artificial intelligence, and software development. Led by Dr. Sarah Chen (Former Head of AI at HealthTech), John Smith (Ex-Google AI Engineer), and Mark Johnson (Healthcare Operations Expert).")
    
    # Financial Projections
    pdf.add_page()
    pdf.set_font("Arial", "B", 20)
    pdf.cell(0, 10, "Financial Projections", align="L")
    pdf.ln(15)
    pdf.set_font("Arial", "", 12)
    pdf.multi_cell(0, 10, "Year 1: $1M revenue (100 customers)\nYear 2: $5M revenue (500 customers)\nYear 3: $15M revenue (1,500 customers)\n\nWe are seeking $2M in funding to accelerate product development and market expansion.")
    
    # Save the PDF
    pdf.output("media/test_pitch_deck.pdf")

if __name__ == "__main__":
    create_test_pitch_deck() 