from pathlib import Path
import csv
base=Path(__file__).resolve().parents[1]/'data/synthetic';base.mkdir(exist_ok=True,parents=True)
fields=['SYNTHETIC_U','ORG_TYPE','MAINOKVED_CODE','MAINOKVED_NAME','REVENUE_COMPANY','CITY','REGION','GROUP_ID','FTS_FLAG','FTS_COUNTRY_NAME','CL_PRODUCT_RKO_MARK','CL_PRODUCT_LOA_MARK','CL_PRODUCT_DEP_MARK','CL_PRODUCT_LEA_MARK','FACTORING_MARK']
rows=[['U_101','КОММ_ОРГ','24.10','Производство стали и металлопродукции','28400000000','Екатеринбург','Свердловская область','DEMO_G1',1,'Китай',1,1,0,1,1],['U_202','КОММ_ОРГ','46.71','Оптовая торговля топливом','41600000000','Москва','Москва','DEMO_G2',1,'Казахстан',1,0,1,0,0],['U_303','КОММ_ОРГ','52.29','Транспортная логистика и перевозки','18700000000','Санкт-Петербург','Санкт-Петербург','DEMO_G1',0,'',1,1,0,1,0]]
with (base/'df_Uid_data_hack.csv').open('w') as f:
 w=csv.writer(f,delimiter=';');w.writerow(fields);w.writerows(rows)
with (base/'df_Fid_Uid_link_hack.csv').open('w') as f:
 w=csv.writer(f,delimiter=';');w.writerow(['SYNTHETIC_F','SYNTHETIC_U','CITY_NAME','RC_NAME']);w.writerows([['F_1','U_101','Екатеринбург','Урал'],['F_1','U_303','Екатеринбург','Урал']])
with (base/'df_Uid_payment_hack.csv').open('w') as f:
 w=csv.writer(f,delimiter=';');w.writerow(['PAYER','BENEFICIARY','PAY_AMT','PAY_CNT']);w.writerows([['U_101','U_303',482000000,120],['U_202','U_101',176000000,38]])
(base/'README.md').write_text('# Синтетические данные\n\nВсе компании, связи, платежи и новости DEMO созданы для проверки интерфейса. Они не описывают реальные организации и не являются прогнозами банка. Единица выручки в тестовых данных — рубли; это не подтверждает единицу официального CSV.\n')
