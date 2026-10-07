"""Small AR(2) ridge model with chronological holdout and persistence fallback.

No GPU, external ML service, or presumed historical observations are involved.
Bands are heuristic error ranges, not calibrated statistical confidence intervals.
"""
from datetime import timedelta
from math import sqrt
from statistics import median
from contracts.analytics import TrafficForecast, ForecastPoint

def solve(matrix, target):
    rows = [list(row)+[value] for row,value in zip(matrix,target)]
    for column in range(len(rows)):
        pivot = max(range(column,len(rows)),key=lambda i:abs(rows[i][column]))
        rows[column],rows[pivot] = rows[pivot],rows[column]
        scale = rows[column][column]
        if abs(scale)<1e-10:
            raise ValueError('Singular forecast')
        rows[column] = [v/scale for v in rows[column]]
        for i in range(len(rows)):
            if i != column:
                amount = rows[i][column]
                rows[i] = [a-amount*b for a,b in zip(rows[i],rows[column])]
    return [row[-1] for row in rows]

def fit(values):
    features = [[1,values[i-1]/100,values[i-2]/100] for i in range(2,len(values))]
    y = [v/100 for v in values[2:]]
    matrix = [[sum(x[i]*x[j] for x in features)+(0.02 if i==j and i else 1e-8 if i==j else 0) for j in range(3)] for i in range(3)]
    return solve(matrix,[sum(x[i]*v for x,v in zip(features,y)) for i in range(3)])

def predict(coefficients, values):
    return max(0,min(100,100*coefficients[0]+coefficients[1]*values[-1]+coefficients[2]*values[-2]))

def forecast(samples, now):
    usable = [s for s in samples if s.confidence>=.5 and not s.road_closed and s.point_distance_m<=250]
    empty = dict(method='none',training_samples=len(usable),validation_mae=None,baseline_mae=None,points=[])
    if not usable:
        return TrafficForecast(state='collecting',message='Prediksi menunggu sampel TomTom yang valid.',**empty)
    if samples[-1] not in usable:
        return TrafficForecast(state='unavailable',message='Sampel terbaru tidak layak atau ruas ditutup; prediksi ditahan.',**empty)
    if (now-usable[-1].observed_at).total_seconds() < -.5:
        return TrafficForecast(state='unavailable',message='Waktu sampel berada di masa depan; prediksi ditahan.',**empty)
    if (now-usable[-1].observed_at).total_seconds()>600:
        return TrafficForecast(state='stale',message='Pengamatan terakhir terlalu lama; prediksi ditahan.',**empty)
    # Use one contiguous segment; do not learn across outages or road closures.
    contiguous = [usable[-1]]
    for sample in reversed(samples[:-1]):
        if sample not in usable: break
        gap = (contiguous[0].observed_at-sample.observed_at).total_seconds()
        if not 30<=gap<=360: break
        contiguous.insert(0,sample)
    contiguous = contiguous[-90:]
    empty['training_samples'] = len(contiguous)
    if len(contiguous)<12:
        return TrafficForecast(state='collecting',message=f'Mengumpulkan pola: {len(contiguous)}/12 sampel berurutan. Tidak ada prediksi buatan.',**empty)
    values = [s.congestion_percent for s in contiguous]
    cut = max(8,int(len(values)*.8))
    model = fit(values[:cut])
    errors = [abs(predict(model,values[:i])-values[i]) for i in range(cut,len(values))]
    baseline = [abs(values[i-1]-values[i]) for i in range(cut,len(values))]
    mae, naive = sum(errors)/len(errors),sum(baseline)/len(baseline)
    use_model = mae<=naive*1.05
    model = fit(values)
    interval = median((b.observed_at-a.observed_at).total_seconds() for a,b in zip(contiguous,contiguous[1:]))
    points, future = [],values[:]
    for step in range(1,int(1800/interval)+1):
        value = predict(model,future) if use_model else values[-1]
        future.append(value)
        width = max(5,(mae if use_model else naive)*1.6)*sqrt(step)
        points.append(ForecastPoint(at=contiguous[-1].observed_at+timedelta(seconds=step*interval),
            congestion_percent=round(value,2),lower=round(max(0,value-width),2),upper=round(min(100,value+width),2)))
    return TrafficForecast(state='ready',method='ridge_ar2' if use_model else 'persistence',training_samples=len(values),
        validation_mae=round(mae if use_model else naive,2),baseline_mae=round(naive,2),points=points,
        message='Regresi autoregresif lokal; rentang berdasarkan galat, belum tervalidasi lapangan.' if use_model else 'Model belum mengungguli nilai terakhir pada uji kronologis; memakai baseline persistence.')
