"""Calculate metrics only from human-supplied graded labels; refuses empty/unjudged sets."""
import csv,math,argparse,json
from collections import defaultdict
p=argparse.ArgumentParser();p.add_argument('labels');p.add_argument('predictions',help='CSV query_id,article_id,score');p.add_argument('-k',type=int,default=5);args=p.parse_args()
if args.k<1:raise SystemExit('K must be positive')
labels=defaultdict(dict)
for row in csv.DictReader(open(args.labels)):
    grade=int(row['relevance'])
    if grade not in range(4):raise SystemExit('Labels must be human-judged relevance 0..3')
    labels[row['query_id']][row['article_id']]=grade
if not labels:raise SystemExit('No human labels: no metrics were computed')
predictions=defaultdict(list)
for row in csv.DictReader(open(args.predictions)):
    score=float(row['score'])
    if not math.isfinite(score):raise SystemExit('Score must be finite')
    predictions[row['query_id']].append((row['article_id'],score))
result=[]
for q,truth in labels.items():
    ranked=sorted(predictions.get(q,[]),key=lambda x:x[1],reverse=True)
    if len({i for i,s in ranked})!=len(ranked):raise SystemExit('Duplicate article IDs in predictions')
    if not ranked or any(i not in truth for i,s in ranked):raise SystemExit('Unjudged candidates: metrics refused')
    top=ranked[:args.k];grades=[truth[i] for i,s in top]
    dcg=sum((2**g-1)/math.log2(j+2) for j,g in enumerate(grades))
    ideal=sum((2**g-1)/math.log2(j+2) for j,g in enumerate(sorted(truth.values(),reverse=True)[:args.k]))
    result.append({'query_id':q,'judged_candidates':len(truth),'returned':len(top),'precision_at_k':sum(g>0 for g in grades)/args.k,'ndcg_at_k':dcg/ideal if ideal else None})
print(json.dumps({'k':args.k,'results':result},ensure_ascii=False,indent=2))
