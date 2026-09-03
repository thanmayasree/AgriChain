from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password
from app.models.entities import Batch, BatchInventory, Customer, Farmer, Order, OrderStage, User
from app.services.chain_service import next_batch_id, record_event

router = APIRouter()
STAGES = [
    ("FARM_HARVEST", "Product registered and harvested by the farmer."),
    ("QUALITY_CHECK", "Product quality and grade recorded."),
    ("PROCESSING", "Required processing completed."),
    ("PACKAGING", "Product packaged for this order."),
    ("WAREHOUSE", "Product stored before dispatch."),
    ("DISPATCH", "Order dispatched toward the customer."),
    ("IN_TRANSIT", "Order moving from source to destination."),
    ("DELIVERED", "Product received by the customer."),
]

class FarmerIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=8, max_length=20)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    farm_name: str = Field(min_length=2, max_length=160)
    location: str = Field(min_length=2, max_length=255)
    district: str = ""; state: str = ""; pincode: str = ""
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)

class BatchIn(BaseModel):
    farmer_id: int
    product: str = Field(min_length=2, max_length=80)
    category: str = "Agricultural Produce"; variety: str = ""
    grade: str = Field(pattern=r"^Grade [123]$")
    quantity: float = Field(gt=0); bags: int = Field(default=0, ge=0)
    quantity_per_bag: float = Field(default=0, ge=0)
    unit: str = Field(default="kg", pattern=r"^(kg|bags)$")
    price_per_unit: float = Field(ge=0)
    harvest_date: str
    source_location: str = Field(min_length=2)
    minimum_order_quantity: float = Field(default=1, gt=0)
    best_before: str = ""; certification: str = ""
    @model_validator(mode="after")
    def bag_values(self):
        if self.unit == "bags" and (self.bags <= 0 or self.quantity_per_bag <= 0):
            raise ValueError("Bag inventory requires bag count and quantity per bag")
        return self

class CustomerIn(BaseModel):
    name: str = Field(min_length=2); phone: str = Field(min_length=8, max_length=20)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    location: str = Field(min_length=2); city: str = ""; district: str = ""; state: str = ""; pincode: str = ""
    delivery_address: str = Field(min_length=5)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)

class OrderIn(BaseModel):
    customer_id: int; batch_id: str
    quantity: float = Field(gt=0); unit: str = Field(default="kg", pattern=r"^(kg|bags)$")
    bags: int = Field(default=0, ge=0); destination: str = Field(min_length=2)
    destination_lat: float | None = Field(default=None, ge=-90, le=90)
    destination_lng: float | None = Field(default=None, ge=-180, le=180)

class StageIn(BaseModel):
    status: str = Field(pattern=r"^(COMPLETED|DELAYED|CANCELLED)$")
    location: str = Field(min_length=2)
    completed_at: datetime | None = None

def distance_km(a,b,c,d):
    p1,p2=math.radians(a),math.radians(c); dp=math.radians(c-a); dl=math.radians(d-b)
    return round(12742*math.asin(math.sqrt(math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2)),1)

def farmer_data(f):
    return {"id":f.id,"farmer_id":f.farmer_code,"name":f.user.full_name,"phone":f.phone,"email":f.user.email,"farm_name":f.farm_name,"location":f.region,"lat":f.lat,"lng":f.lng,"status":"VERIFIED","registered_at":f.user.created_at.isoformat()}

def order_data(db,o,private=False):
    b=o.batch; inv=db.query(BatchInventory).filter_by(batch_id=b.id).first()
    rows=db.query(OrderStage).filter_by(order_id=o.id).order_by(OrderStage.stage_index).all()
    stages=[]
    for s in rows:
        delay=max(0,round((s.completed_at-s.expected_at).total_seconds()/3600,2)) if s.completed_at and s.expected_at else None
        stages.append({"index":s.stage_index,"name":s.name,"status":s.status,"eta":s.expected_at.isoformat() if s.expected_at else None,"actual":s.completed_at.isoformat() if s.completed_at else None,"delay_hours":delay,"location":s.location,"description":s.description,"block_index":s.block_index,"block_hash":s.block_hash})
    return {"order_id":o.order_id,"customer":{"id":o.customer.id,"name":"Previous customer" if private else o.customer.name,"location":o.customer.city or o.customer.location},"farmer":{"id":b.farmer_id,"name":b.farmer_name,"location":b.origin},"batch":{"batch_id":b.batch_id,"product":b.crop,"variety":b.variety,"grade":inv.grade if inv else b.quality_grade,"available_quantity":inv.available_quantity if inv else b.quantity_kg},"quantity":o.ordered_quantity,"unit":o.unit,"bags":o.bags,"price_per_unit":o.price_per_unit,"total_amount":o.total_amount,"source":o.source,"destination":o.destination,"distance_km":o.distance_km,"estimated_travel_hours":o.travel_hours,"estimated_delivery":o.estimated_delivery.isoformat() if o.estimated_delivery else None,"actual_delivery":o.actual_delivery.isoformat() if o.actual_delivery else None,"status":o.status,"created_at":o.created_at.isoformat(),"stages":stages}

@router.post("/farmers/register", status_code=201)
def create_farmer(body:FarmerIn, db:Session=Depends(get_db)):
    if db.query(User).filter_by(email=body.email.lower()).first(): raise HTTPException(409,"Email already registered")
    u=User(email=body.email.lower(),full_name=body.name,hashed_password=hash_password(uuid4().hex),role="FARMER",organization=body.farm_name,location=body.location)
    db.add(u); db.flush(); f=Farmer(user_id=u.id,farmer_code=f"FARM-{datetime.now().year}-{db.query(Farmer).count()+1:04d}",farm_name=body.farm_name,region=body.location,village=", ".join(x for x in [body.district,body.state,body.pincode] if x),lat=body.lat or 0,lng=body.lng or 0,phone=body.phone)
    db.add(f); db.commit(); db.refresh(f); return farmer_data(f)

@router.get("/farmers/public")
def farmers(db:Session=Depends(get_db)): return [farmer_data(f) for f in db.query(Farmer).all()]

@router.post("/market/batches", status_code=201)
def create_batch(body:BatchIn, db:Session=Depends(get_db)):
    f=db.query(Farmer).filter_by(id=body.farmer_id).first()
    if not f: raise HTTPException(404,"Farmer not found")
    b=Batch(batch_id=next_batch_id(db,body.product,body.source_location),crop=body.product,variety=body.variety,quantity_kg=body.quantity,harvest_date=body.harvest_date,origin=body.source_location,farmer_id=f.id,farmer_name=f.user.full_name,current_location=body.source_location,quality_grade=body.grade,farmer_price=body.price_per_unit,verification_status="REGISTERED")
    db.add(b); db.flush(); db.add(BatchInventory(batch_id=b.id,category=body.category,grade=body.grade,bags=body.bags,quantity_per_bag=body.quantity_per_bag,unit=body.unit,available_quantity=body.quantity,minimum_order_quantity=body.minimum_order_quantity,price_per_unit=body.price_per_unit,best_before=body.best_before,certification=body.certification,status="AVAILABLE")); db.commit()
    receipt=record_event(db,batch=b,event_type="HARVEST",actor_email=f.user.email,actor_role="FARMER",location=b.origin,metadata={"quantity":body.quantity,"grade":body.grade,"bags":body.bags})
    return {"message":"Batch created and harvest anchored","batch_id":b.batch_id,"block_hash":receipt["block_hash"]}

@router.get("/market/batches")
def batches(product:str|None=None,db:Session=Depends(get_db)):
    q=db.query(Batch); q=q.filter(Batch.crop.ilike(product)) if product else q; out=[]
    for b in q.all():
        i=db.query(BatchInventory).filter_by(batch_id=b.id).first(); out.append({"batch_id":b.batch_id,"product":b.crop,"variety":b.variety,"farmer_id":b.farmer_id,"farmer":b.farmer_name,"source":b.origin,"grade":i.grade if i else b.quality_grade,"available_quantity":i.available_quantity if i else b.quantity_kg,"unit":i.unit if i else "kg","bags":i.bags if i else 0,"quantity_per_bag":i.quantity_per_bag if i else 0,"minimum_order_quantity":i.minimum_order_quantity if i else 1,"price_per_unit":i.price_per_unit if i else b.farmer_price,"is_demo":i.is_demo if i else True})
    return {"items":out,"total":len(out)}

@router.post("/customers",status_code=201)
def create_customer(body:CustomerIn,db:Session=Depends(get_db)):
    if db.query(Customer).filter_by(email=body.email.lower()).first(): raise HTTPException(409,"Customer email already registered")
    c=Customer(customer_code=f"CUST-{datetime.now().year}-{db.query(Customer).count()+1:04d}",name=body.name,phone=body.phone,email=body.email.lower(),location=body.location,city=body.city,district=body.district,state=body.state,pincode=body.pincode,delivery_address=body.delivery_address,lat=body.lat,lng=body.lng)
    db.add(c);db.commit();db.refresh(c);return {"id":c.id,"customer_id":c.customer_code,"name":c.name,"location":c.location,"registered_at":c.created_at.isoformat()}

@router.get("/customers")
def customers(db:Session=Depends(get_db)): return [{"id":c.id,"customer_id":c.customer_code,"name":c.name,"location":c.location,"city":c.city} for c in db.query(Customer).all()]

@router.post("/orders",status_code=201)
def create_order(body:OrderIn,db:Session=Depends(get_db)):
    c=db.query(Customer).filter_by(id=body.customer_id).first(); b=db.query(Batch).filter_by(batch_id=body.batch_id).first()
    if not c: raise HTTPException(404,"Customer not found")
    if not b: raise HTTPException(404,"Batch not found")
    i=db.query(BatchInventory).filter_by(batch_id=b.id).first(); available=i.available_quantity if i else b.quantity_kg
    if body.unit=="bags" and (not i or i.quantity_per_bag<=0): raise HTTPException(400,"This batch does not define a bag size")
    requested=body.quantity*(i.quantity_per_bag if body.unit=="bags" else 1)
    if requested>(available or 0): raise HTTPException(400,f"Only {available} kg is available")
    lat=body.destination_lat if body.destination_lat is not None else c.lat; lng=body.destination_lng if body.destination_lng is not None else c.lng
    f=db.query(Farmer).filter_by(id=b.farmer_id).first() if b.farmer_id else None
    dist=distance_km(f.lat,f.lng,lat,lng) if f and f.lat and f.lng and lat is not None and lng is not None else None
    travel=round(dist/45+1.5,1) if dist is not None else None; now=datetime.now(timezone.utc); eta=now+timedelta(hours=(travel or 24)+18); price=i.price_per_unit if i else b.farmer_price
    o=Order(order_id=f"ORD-{now.year}-{db.query(Order).count()+1:05d}",customer_id=c.id,batch_id=b.id,ordered_quantity=body.quantity,unit=body.unit,bags=body.bags,price_per_unit=price,total_amount=round(requested*price,2),source=b.origin,destination=body.destination,distance_km=dist,travel_hours=travel,estimated_delivery=eta,status="CONFIRMED")
    db.add(o);db.flush()
    for n,(name,desc) in enumerate(STAGES,1): db.add(OrderStage(order_id=o.id,stage_index=n,name=name,status="COMPLETED" if n==1 else "PENDING",expected_at=now+timedelta(hours=n*(3+(travel or 12)/8)),completed_at=now if n==1 else None,location=b.origin if n==1 else "",description=desc))
    if i:i.available_quantity-=requested
    db.commit(); receipt=record_event(db,batch=b,event_type="ORDER_CREATED",actor_email=c.email,actor_role="CUSTOMER",location=body.destination,metadata={"order_id":o.order_id,"quantity":body.quantity,"unit":body.unit,"eta":eta.isoformat()})
    first=db.query(OrderStage).filter_by(order_id=o.id,stage_index=1).first();first.block_index=receipt["block_index"];first.block_hash=receipt["block_hash"];db.commit();db.refresh(o);return order_data(db,o)

@router.get("/orders")
def orders(customer_id:int|None=None,farmer_id:int|None=None,db:Session=Depends(get_db)):
    q=db.query(Order)
    if customer_id:q=q.filter(Order.customer_id==customer_id)
    if farmer_id:q=q.join(Batch).filter(Batch.farmer_id==farmer_id)
    rows=q.order_by(Order.id.desc()).all();return {"items":[order_data(db,o) for o in rows],"total":len(rows)}

@router.get("/orders/{order_id}")
@router.get("/orders/{order_id}/traceability")
def order(order_id:str,db:Session=Depends(get_db)):
    o=db.query(Order).filter_by(order_id=order_id).first()
    if not o: raise HTTPException(404,"Order not found")
    previous=db.query(Order).join(Batch).filter(Batch.farmer_id==o.batch.farmer_id,Order.id!=o.id).order_by(Order.id.desc()).limit(8).all(); result=order_data(db,o);result["previous_supply_history"]=[order_data(db,x,True) for x in previous];return result

@router.put("/orders/{order_id}/stages/{stage_index}")
def stage(order_id:str,stage_index:int,body:StageIn,db:Session=Depends(get_db)):
    o=db.query(Order).filter_by(order_id=order_id).first()
    if not o or stage_index not in range(1,9): raise HTTPException(404,"Order or stage not found")
    s=db.query(OrderStage).filter_by(order_id=o.id,stage_index=stage_index).first(); done=body.completed_at or datetime.now(timezone.utc);s.completed_at=done;s.location=body.location;s.status="DELAYED" if s.expected_at and done>s.expected_at else body.status
    receipt=record_event(db,batch=o.batch,event_type=s.name,actor_email="supply-chain@agrichain.local",actor_role="OPERATOR",location=body.location,metadata={"order_id":o.order_id,"stage":stage_index});s.block_index=receipt["block_index"];s.block_hash=receipt["block_hash"];o.status="DELIVERED" if stage_index==8 else s.name;o.actual_delivery=done if stage_index==8 else o.actual_delivery;db.commit();return order_data(db,o)

@router.get("/commerce/analytics")
def commerce_analytics(db:Session=Depends(get_db)):
    rows=db.query(Order).all(); delivered=[o for o in rows if o.actual_delivery]; delayed=[o for o in delivered if o.estimated_delivery and o.actual_delivery>o.estimated_delivery]
    return {"orders":len(rows),"active":sum(o.status not in {"DELIVERED","CANCELLED"} for o in rows),"delivered":len(delivered),"delayed":len(delayed),"quantity":sum(o.ordered_quantity for o in rows),"amount":sum(o.total_amount for o in rows),"on_time":len(delivered)-len(delayed),"average_delivery_hours":round(sum((o.actual_delivery-o.created_at).total_seconds()/3600 for o in delivered)/max(1,len(delivered)),1),"average_delay_hours":round(sum(max(0,(o.actual_delivery-o.estimated_delivery).total_seconds()/3600) for o in delayed)/max(1,len(delayed)),1)}
