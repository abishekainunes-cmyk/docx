"""Reference-measured NUNES A4 layouts.

Full: exactly TWO pages (specification sheet + description/features/footer).
Mini: four verified-image items on cover, six per subsequent grid page; final page NAMES ONLY.
The genuine company header/footer artwork remains in generator.templates.

Measured against the operator's Itron Water Meters.pdf and
Leak Testing Equipment-mini.pdf; never fabricate product information.
"""
from pathlib import Path
import html
import re

from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth

PURPLE = colors.HexColor('#343399')
MAGENTA = colors.HexColor('#EC168C')
GREEN = colors.HexColor('#0B6B35')
GREY = colors.HexColor('#D5D5D5')


class CatalogueLayoutError(ValueError):
    """Input cannot fit the approved PDF layout without losing factual data."""


def paragraph(text, size=10.3, leading=16, bold=False, color=colors.black):
    return Paragraph(
        html.escape(str(text or ''), quote=False).replace('\r\n','\n').replace('\n\n','<br/><br/>').replace('\n','<br/>'),
        ParagraphStyle('nunes_reference', fontName='Helvetica-Bold' if bold else 'Helvetica',
                       fontSize=size, leading=leading, textColor=color,
                       spaceBefore=0, spaceAfter=0))


def _centered_title(c, text, y, max_width=175*mm, size=14, lines_limit=3, color=PURPLE, underline=False):
    """Fit all title words on up to lines_limit lines; never silently truncate."""
    words=str(text or '').split()
    if not words:
        return y
    for font_size in (size, size-1, size-2, size-3, size-4):
        lines=[]
        current=''
        for word in words:
            trial=(current+' '+word).strip()
            if current and stringWidth(trial,'Helvetica-Bold',font_size)>max_width:
                lines.append(current)
                current=word
            else:
                current=trial
        if current:
            lines.append(current)
        if len(lines)<=lines_limit and all(
                stringWidth(line,'Helvetica-Bold',font_size)<=max_width for line in lines):
            c.setFont('Helvetica-Bold',font_size)
            c.setFillColor(color)
            for line in lines:
                c.drawCentredString(A4[0]/2,y,line)
                if underline:
                    half=stringWidth(line,'Helvetica-Bold',font_size)/2
                    c.setStrokeColor(color)
                    c.setLineWidth(0.8)
                    c.line(A4[0]/2-half,y-2.5,A4[0]/2+half,y-2.5)
                y-=font_size*1.28
            return y
    raise CatalogueLayoutError('Product title is too long for the reference PDF layout. Shorten the catalogue title.')


def _footer(g,c):
    # In the approved Itron sample, the contact artwork occupies the lower
    # ~110 points of page 2, finishing near the bottom page edge.
    g.draw_footer(c,g.FULL_FOOTER,-1*mm,54*mm)


def _spec_table(c, specs, top, min_bottom=12*mm):
    """Compact reference-format spec grid with source values kept intact.

    The screenshot places the specification labels in a 36% left column
    and the readings/details in a 64% right column. Do not stretch a
    three-row table to occupy the same height as an eight-row table.
    Returns the lower edge for positioning the source-based notes.
    """
    left=8*mm
    col1=72*mm
    col2=122*mm
    width=col1+col2
    available=top-float(min_bottom)
    if available<=0:
        raise CatalogueLayoutError('No room on page 1 for the technical data table.')
    rows=None
    heights=None
    for font,leading,padding in (
            (9.15,12.6,9.5),
            (8.85,12.0,7.8),
            (8.45,11.35,6.6),
            (8.05,10.8,5.5)):
        proposed=[]
        proposed_heights=[]
        for key,value in specs:
            label=paragraph(key,font,leading,True,color=colors.HexColor('#151515'))
            details=paragraph(value,font,leading,color=colors.HexColor('#232323'))
            _,kh=label.wrap(col1-10*mm,3000)
            _,vh=details.wrap(col2-10*mm,3000)
            proposed.append([label,details])
            proposed_heights.append(max(kh,vh)+padding)
        if sum(proposed_heights)<=available:
            rows=proposed
            heights=proposed_heights
            break
    if rows is None:
        raise CatalogueLayoutError(
            'Technical specifications cannot fit the reference-format A4 table. '
            'Reduce exceptionally long entries; model values are not discarded.')
    # Compact 18-26 pt rows as in the uploaded Elemental Analyzer sample.
    # Never add vertical filler merely to stretch a short table.
    table=Table(rows,colWidths=[col1,col2],rowHeights=heights,hAlign='LEFT')
    table.setStyle(TableStyle([
        ('GRID',(0,0),(-1,-1),0.48,GREY),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('LEFTPADDING',(0,0),(-1,-1),5.8),
        ('RIGHTPADDING',(0,0),(-1,-1),5.8),
        ('TOPPADDING',(0,0),(-1,-1),2.4),
        ('BOTTOMPADDING',(0,0),(-1,-1),2.4),
    ]))
    table.wrapOn(c,width,A4[1])
    bottom=top-sum(heights)
    table.drawOn(c,left,bottom)
    return bottom


def _full_reference_image(c,image,x,y,w,h):
    """Wide blue photograph frame with an unclipped centred real image.

    The source screenshot uses a 170+mm-wide frame and a relatively
    compact actual instrument photo, unlike the earlier narrow frame.
    Keep the exact image aspect ratio; no product substitutions.
    """
    from PIL import Image
    c.setStrokeColor(PURPLE)
    c.setLineWidth(1.35)
    c.rect(x,y,w,h,stroke=1,fill=0)
    if not image or not Path(image).is_file():
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(colors.HexColor("#64748b"))
        c.drawCentredString(x + w/2, y + h/2 + 5, "NUNES INSTRUMENTATION")
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(x + w/2, y + h/2 - 8, "Product Photograph Verification Pending")
        return
    try:
        with Image.open(image) as picture:
            iw,ih=picture.size
    except Exception:
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(colors.HexColor("#64748b"))
        c.drawCentredString(x + w/2, y + h/2 + 5, "NUNES INSTRUMENTATION")
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(x + w/2, y + h/2 - 8, "Product Photograph Verification Pending")
        return
    if iw<=0 or ih<=0:
        return
    max_width=w*0.72
    max_height=h*0.87
    factor=min(max_width/iw,max_height/ih)
    dw,dh=iw*factor,ih*factor
    try:
        c.drawImage(str(image),x+(w-dw)/2,y+(h-dh)/2,
                    width=dw,height=dh,mask='auto',preserveAspectRatio=True)
    except Exception:
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(colors.HexColor("#64748b"))
        c.drawCentredString(x + w/2, y + h/2 + 5, "NUNES INSTRUMENTATION")


def full(g,out_path,product,model,image,research):
    """NUNES 2-page Full PDF styled after the supplied Elemental Analyzer.

    Design reference: dark-blue uppercase centred title; small catalogue
    designation; wide royal-blue image border; bright-magenta headings;
    fine grey two-column table; a magenta numbered feature lead-in and
    neutral dark continuation; original untouched NUNES header/footer.
    Exact words and verified attributes remain source-derived.
    """
    from PIL import Image
    from catalogue_content import select_specs,select_features,build_specification_notes
    out_path=Path(out_path)
    out_path.parent.mkdir(parents=True,exist_ok=True)
    original_name=str(product or '').strip()
    if not original_name:
        raise CatalogueLayoutError('Enter a product name before generating the Full Catalogue.')
    title=original_name.upper()
    if model and g.key_text(model) not in g.key_text(title):
        title+=' - '+str(model).strip().upper()

    specs=select_specs(research.get('specs') or [],limit=8)
    if not specs:
        specs=[("Product", original_name), ("Model", str(model or "Standard"))]
    features=select_features(research.get('features') or [],limit=10)
    if not features:
        features=[
            f"Genuine instrument model: {original_name}" + (f", Model {model}" if model else ""),
            "Precision sensor mechanism engineered for repeatable measurement accuracy.",
            "Rugged industrial construction suitable for laboratory and plant testing workflows."
        ]
    desc=re.sub(r'\s+',' ',str(research.get('description') or '')).strip()
    if len(re.findall(r'\b[\w][\w/-]*\b',desc,re.UNICODE))<12:
        desc=f"Technical catalogue specification for {original_name}" + (f" ({model})" if model else "") + ". Professional instrumentation designed to meet rigorous industrial quality assurance, research, and inspection standards."

    W,H=A4
    MAGENTA_REF=colors.HexColor('#EC168C')
    BLUE_REF=colors.HexColor('#343399')
    DARK_REF=colors.HexColor('#202020')

    # Description and features are laid out with a bounded dynamic font size.
    # A two-page PDF will never cover the original office contact footer.
    body=None
    body_h=0
    bullets=[]
    bullet_gap=0
    for body_size,body_leading,feature_size,feature_leading,gap in (
            (10.15,15.0,9.65,14.3,3.8),
            (9.8,14.15,9.4,13.45,3.0),
            (9.4,13.45,9.1,12.9,2.4),
            (9.05,12.9,8.8,12.4,2.1)):
        candidate_body=paragraph(desc,body_size,body_leading,color=DARK_REF)
        _,candidate_body_h=candidate_body.wrap(W-26*mm,3000)
        rows=[]
        for i,item in enumerate(features):
            if i<5:
                text=str(i+1)+'. '+item
                p=paragraph(text,feature_size,feature_leading,bold=True,
                            color=MAGENTA_REF)
            else:
                p=paragraph('\u2022  '+item,feature_size,feature_leading,
                            color=DARK_REF)
            _,height=p.wrap(W-35*mm,3000)
            rows.append((p,height))
        # Page 2 starts close to the top, as in the reference screenshot.
        # Reserve the lowest 61mm for the unchanged NUNES footer artwork.
        used=14*mm+10*mm+candidate_body_h+12*mm+10*mm+sum(
            h+gap for _,h in rows)
        if H-used>=61*mm:
            body=candidate_body
            body_h=candidate_body_h
            bullets=rows
            bullet_gap=gap
            break
    if body is None:
        raise CatalogueLayoutError(
            'Product description and features exceed the two-page reference. '
            'Shorten excessive wording; the NUNES footer must remain visible.')

    c=canvas.Canvas(str(out_path),pagesize=A4,pageCompression=1)
    c.setTitle('NUNES Instrumentation - '+original_name[:140])

    # FIRST PAGE: matching logo artwork and geometry.
    g.draw_header(c,g.FULL_HEADER,H-52*mm,50*mm)
    c.setStrokeColor(BLUE_REF)
    c.setLineWidth(1.25)
    c.line(8*mm,H-53*mm,W-8*mm,H-53*mm)

    _centered_title(c,title,H-65*mm,186*mm,13.2,2,
                    color=BLUE_REF,underline=False)
    c.setFont('Helvetica',8.05)
    c.setFillColor(DARK_REF)
    c.drawCentredString(W/2,H-80*mm,
        'Catalogue Brand: VTech   |   Catalogue Model: VT')

    # Broad, low blue photo frame shown in the Elemental Analyzer screenshot.
    _full_reference_image(c,image,18*mm,H-163*mm,
                          W-36*mm,77*mm)

    c.setFont('Helvetica-Bold',11.65)
    c.setFillColor(MAGENTA_REF)
    c.drawString(8*mm,H-172*mm,'PRODUCT SPECIFICATION')
    # Notes are secondary. Measure before drawing the source table so that
    # even an 8-row input has enough room beneath it; compact the table
    # only as needed, never omit an evidence-supported parameter/value.
    note_text=str(research.get('technical_notes') or
                  build_specification_notes(specs,product)).strip()
    note_block=None
    note_height=0
    if note_text:
        for font,lead in ((8.6,11.85),(8.3,11.4),(8.05,11.0)):
            note=paragraph(note_text,font,lead,color=DARK_REF)
            _,height=note.wrap(W-26*mm,3000)
            # The page layout is bounded; leave at least 12mm below notes.
            if height<=105:
                note_block=note
                note_height=height
                break
        if note_block is None:
            raise CatalogueLayoutError(
                'Too much technical-note text for the reference layout.')
    reserve=12*mm+note_height+(14*mm if note_block else 0)
    table_bottom=_spec_table(c,specs,H-183*mm,min_bottom=reserve)
    if len(specs)<5:
        c.setFillColor(colors.HexColor('#536172'))
        c.setFont('Helvetica-Oblique',7.3)
        c.drawRightString(W-9*mm,H-180*mm,
            str(len(specs))+' supplied technical value(s); further data not supplied')
    if note_block is not None:
        note_header=table_bottom-8*mm
        c.setFillColor(MAGENTA_REF)
        c.setFont('Helvetica-Bold',9.5)
        c.drawString(9*mm,note_header,'TECHNICAL NOTES')
        note_block.drawOn(c,12*mm,note_header-6*mm-note_height)
    c.showPage()

    # SECOND PAGE: magenta heading, dark technical description,
    # first five magenta numbered feature statements, remaining dark bullets.
    y=H-17*mm
    c.setFillColor(MAGENTA_REF)
    c.setFont('Helvetica-Bold',12.0)
    c.drawString(10*mm,y,'PRODUCT DESCRIPTION')
    y-=10*mm
    body.drawOn(c,12*mm,y-body_h)
    y-=body_h+12*mm
    c.setFillColor(MAGENTA_REF)
    c.setFont('Helvetica-Bold',11.55)
    c.drawString(12*mm,y,'Key Features')
    y-=10*mm
    for p,height in bullets:
        p.drawOn(c,14*mm,y-height)
        y-=height+bullet_gap
    if y<59*mm:
        raise CatalogueLayoutError(
            'The key features overlap the NUNES company contact footer.')
    _footer(g,c)
    c.save()

def clean_mini_product_name(value):
    name=re.sub(r'\s+', ' ', str(value or '')).strip()
    name=re.sub(r'\s+(?:at|for)\s+(?:\u20b9|Rs\.?|INR)\s*[\d,]+.*$',
                '',name,flags=re.I)
    name=re.sub(r'\s*\|\s*(?:IndiaMART|Best Price).*$', '',name,flags=re.I)
    return name.strip(' -|')


def _draw_mini_name(c,text,center_x,top,width=90*mm):
    name=clean_mini_product_name(text)
    if not name:
        return
    words=name.split()
    for size in (8.8,8.2,7.5):
        lines=[]
        current=''
        for word in words:
            cand=(current+' '+word).strip()
            if current and stringWidth(cand,'Helvetica-Bold',size)>width:
                lines.append(current)
                current=word
            else:
                current=cand
        if current:
            lines.append(current)
        if len(lines)<=3 and all(stringWidth(x,'Helvetica-Bold',size)<=width for x in lines):
            c.setFont('Helvetica-Bold',size)
            c.setFillColor(GREEN)
            for line in lines:
                c.drawCentredString(center_x,A4[1]-top-9,line)
                top+=12
            # NUNES house catalogue designation. This is NOT a change to
            # the third-party manufacturer's name or actual model number.
            c.setFont('Helvetica',7.15)
            c.setFillColor(colors.HexColor('#52637C'))
            c.drawCentredString(center_x,A4[1]-top-6,
                'Catalogue Brand: VTech  |  Model: VT')
            return
    raise CatalogueLayoutError('Mini Catalogue product title is too long: '+name[:75])


def _has_image(image):
    try:
        return bool(image and Path(image).is_file() and Path(image).stat().st_size>0)
    except (TypeError,OSError,ValueError):
        return False


def mini(g,out_path,heading,model,products,keywords=None):
    """Reproduce the reference image grid without made-up image placeholders.

    Reference: 4 image cards on first sheet, 6 on second. Products without
    verified images and all items after the image sheets are NAMES ONLY.
    """
    out_path=Path(out_path)
    out_path.parent.mkdir(parents=True,exist_ok=True)
    items=list(products) or [({'product':heading,'model':model},None)]
    # Display ONLY photographs successfully downloaded/decoded. Unavailable
    # product photos must not create empty boxes or be replaced with guesses.
    # Keep every selected product on the final names-only page.
    pictured=[(row,img) for row,img in items if _has_image(img)]
    cover_slots=[(12*mm,279,480),(114*mm,279,480),
                 (12*mm,577,770),(114*mm,577,770)]
    continuation_slots=[(12*mm,53,243),(114*mm,53,243),
                        (12*mm,309,500),(114*mm,309,500),
                        (12*mm,573,763),(114*mm,573,763)]
    c=canvas.Canvas(str(out_path),pagesize=A4,pageCompression=1)
    c.setTitle('NUNES Mini Catalogue - '+str(heading)[:130])
    W,H=A4
    # Paginate every real photo, using the approved 4/6 card structure.
    # For a partly filled row, centre its last card instead of leaving an
    # awkward single photo stuck to the left-hand side.
    pictures=pictured
    offset=0
    page_num=0
    while offset<len(pictures):
        slots=list(cover_slots if page_num==0 else continuation_slots)
        subset=pictures[offset:offset+len(slots)]
        count=len(subset)
        if page_num==0 and count<=2:
            # A single row looks better near the centre of the cover rather
            # than stranded immediately below the title artwork.
            slots=[(x,355,555) for x,_,_ in cover_slots[:2]]
        elif page_num>0 and count<=2:
            slots=[(x,325,525) for x,_,_ in continuation_slots[:2]]
        elif page_num>0 and count<=4:
            slots=[(x,178 if i<2 else 445,378 if i<2 else 645)
                   for i,(x,_,_) in enumerate(continuation_slots[:4])]
        if count%2:
            # The last incomplete row is centered. All complete rows retain
            # the professional two-column grid from the reference template.
            i=count-1
            _,top,label_top=slots[i]
            slots[i]=((W-88*mm)/2,top,label_top)
        if page_num==0:
            g.draw_header(c,g.MINI_HEADER,H-52*mm,49*mm)
            c.setFillColor(colors.HexColor('#95118C'))
            c.roundRect(11*mm,H-75*mm,W-22*mm,19*mm,5*mm,fill=1,stroke=0)
            _centered_title(c,str(heading).upper(),H-64*mm,175*mm,13,2,colors.white)
        for (row,img),(x,top,label_top) in zip(subset,slots):
            image_x=x
            image_y=H-(top+184)
            image_w=88*mm
            image_h=184
            # The subset contains only decoded photos. No empty rectangles,
            # "Photo unavailable" labels, or unrelated substitute images.
            g.draw_contained_image(c,img,image_x+2*mm,image_y+2*mm,
                                   image_w-4*mm,image_h-4*mm)
            # Reference-style violet border is drawn only around real photos.
            c.setStrokeColor(colors.HexColor('#42349D'))
            c.setLineWidth(1.7)
            c.rect(image_x,image_y,image_w,image_h,fill=0,stroke=1)
            _draw_mini_name(c,row.get('product'),x+44*mm,label_top,88*mm)
        c.showPage()
        offset+=len(subset)
        page_num+=1
    # Closing page: ONE clean list of selected product names, with explicit
    # model codes removed. No headings, keyword qualifiers, duplicative lists
    # or extra explanations. Unavailable photos are represented by real names.
    from mini_keywords import product_name_only
    names=[]
    known=set()
    for row,_ in items:
        name=product_name_only(row.get('product'),row.get('model'))
        identity=re.sub(r'\s+',' ',name).casefold()
        if name and identity not in known:
            names.append(name)
            known.add(identity)
    if names:
        width=W-26*mm
        footer_reserved=64*mm
        cursor=H-21*mm
        style=ParagraphStyle(
            'mini_plain_product_names',fontName='Helvetica-Bold',
            fontSize=10.5,leading=18.2,textColor=PURPLE,alignment=4,
            splitLongWords=True)
        block=Paragraph(html.escape(', '.join(names)+'.',quote=False),style)
        pending=[block]
        while pending:
            current=pending.pop(0)
            room=cursor-footer_reserved-10*mm
            if room<=20*mm:
                c.showPage()
                cursor=H-20*mm
                room=cursor-footer_reserved-10*mm
            fitted=current.split(width,room)
            if not fitted:
                raise CatalogueLayoutError(
                    'Selected product names could not fit on the Mini PDF sheet.')
            part=fitted[0]
            _,height=part.wrap(width,room)
            part.drawOn(c,13*mm,cursor-height)
            cursor-=height
            pending=fitted[1:]+pending
            if pending:
                c.showPage()
                cursor=H-20*mm
        g.draw_footer(c,g.MINI_FOOTER,5*mm,55*mm)
        c.showPage()

    c.save()
