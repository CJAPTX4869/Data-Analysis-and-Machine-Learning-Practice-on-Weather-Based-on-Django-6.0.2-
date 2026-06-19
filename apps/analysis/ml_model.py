"""
天气预测机器学习多模型引擎
支持: 线性回归、随机森林、梯度提升、SVR、集成平均
特征: 季节性编码 + 滞后温度 + 滚动统计 + 星期
"""
import numpy as np
from datetime import datetime, timedelta
from typing import Optional

from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.svm import SVR
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

from apps.weather.models import City, WeatherData

# 可用模型注册表（参数已调优）
MODEL_REGISTRY = {
    'linear': {
        'name': '线性回归',
        'icon': 'bi-graph-up',
        'color': '#5470c6',
        'cls': LinearRegression,
        'params': {},
        'needs_scaling': False,
    },
    'randomforest': {
        'name': '随机森林',
        'icon': 'bi-tree-fill',
        'color': '#91cc75',
        'cls': RandomForestRegressor,
        'params': {'n_estimators': 500, 'max_depth': 15, 'min_samples_split': 2,
                   'min_samples_leaf': 1, 'max_features': 'sqrt',
                   'random_state': 42, 'n_jobs': -1},
        'needs_scaling': False,
    },
    'gradientboost': {
        'name': '梯度提升',
        'icon': 'bi-rocket-takeoff',
        'color': '#fac858',
        'cls': GradientBoostingRegressor,
        'params': {'n_estimators': 300, 'learning_rate': 0.05, 'max_depth': 5,
                   'min_samples_split': 4, 'min_samples_leaf': 2,
                   'subsample': 0.8, 'random_state': 42},
        'needs_scaling': False,
    },
    'svr': {
        'name': '支持向量回归(SVR)',
        'icon': 'bi-bullseye',
        'color': '#ee6666',
        'cls': SVR,
        'params': {'kernel': 'rbf', 'C': 10, 'gamma': 'scale', 'epsilon': 0.1},
        'needs_scaling': True,  # SVR 必须缩放
    },
}

# 构建训练特征时用前 N 天作为滞后
LAG_DAYS = [1, 2, 3, 7]          # 前1/2/3/7天的温度
ROLLING_DAYS = 7                  # 7天滚动均值


def _extract_features(records, index):
    """
    从历史记录提取单条特征（无数据泄漏）
    records: WeatherData 列表，按 date 升序
    index: 当前记录索引（>= max(LAG_DAYS)）
    """
    r = records[index]
    doy = r.date.timetuple().tm_yday
    weekday = r.date.weekday()

    feats = [
        # 季节性编码
        np.sin(2 * np.pi * doy / 365),
        np.cos(2 * np.pi * doy / 365),
        r.date.month / 12.0,
        weekday / 6.0,

        # 滞后温度（前1/2/3/7天）
        records[index - 1].temperature_high,
        records[index - 1].temperature_low,
        records[index - 2].temperature_high,
        records[index - 2].temperature_low,
        records[index - 3].temperature_high,
        records[index - 3].temperature_low,
        records[index - 7].temperature_high,
        records[index - 7].temperature_low,

        # 7天滚动均值（不含当日）
        np.mean([records[j].temperature_high for j in range(index - 7, index)]),
        np.mean([records[j].temperature_low for j in range(index - 7, index)]),

        # 7天变化趋势
        records[index - 1].temperature_high - records[index - 7].temperature_high,
        records[index - 1].temperature_low - records[index - 7].temperature_low,
    ]
    return np.array(feats, dtype=np.float64)


def _build_prediction_features(recent_records, future_date, predicted_so_far):
    """
    构建预测用特征（使用最近真实数据 + 已预测的未来数据）
    recent_records: 最近 N 天真实 WeatherData，按 date 升序，至少 7 条
    future_date: 要预测的日期
    predicted_so_far: [(high, low), ...] 已预测的未来天数据
    """
    doy = future_date.timetuple().tm_yday
    weekday = future_date.weekday()

    # 构建虚拟记录列表: 真实 + 已预测
    all_highs = [r.temperature_high for r in recent_records]
    all_lows = [r.temperature_low for r in recent_records]
    for ph, pl in predicted_so_far:
        all_highs.append(ph)
        all_lows.append(pl)

    # 索引：当前记录在虚拟列表中的位置
    cur_idx = len(all_highs) - 1  # 刚追加的预测记录

    # 滞后特征（从虚拟列表中取）
    def lag_high(offset):
        idx = cur_idx - offset
        if idx >= 0 and idx < len(all_highs):
            return float(all_highs[idx])
        # 回退到最近已知值
        return float(recent_records[-1].temperature_high)

    def lag_low(offset):
        idx = cur_idx - offset
        if idx >= 0 and idx < len(all_lows):
            return float(all_lows[idx])
        return float(recent_records[-1].temperature_low)

    # 滚动均值（取最近7个虚拟点的均值）
    start_idx = max(0, cur_idx - 7)
    roll_highs = all_highs[start_idx:cur_idx]
    roll_lows = all_lows[start_idx:cur_idx]
    mean_high = float(np.mean(roll_highs)) if roll_highs else float(recent_records[-1].temperature_high)
    mean_low = float(np.mean(roll_lows)) if roll_lows else float(recent_records[-1].temperature_low)

    feats = [
        np.sin(2 * np.pi * doy / 365),
        np.cos(2 * np.pi * doy / 365),
        future_date.month / 12.0,
        weekday / 6.0,

        lag_high(1), lag_low(1),
        lag_high(2), lag_low(2),
        lag_high(3), lag_low(3),
        lag_high(7), lag_low(7),

        mean_high, mean_low,

        lag_high(1) - lag_high(7),
        lag_low(1) - lag_low(7),
    ]
    return np.array(feats, dtype=np.float64).reshape(1, -1)


class MultiModelPredictor:
    """多模型天气温度预测器（带滞后特征 + 滚动预测）"""

    def __init__(self):
        self.models = {}         # key -> {'high': model, 'low': model}
        self.scalers = {}        # key -> StandardScaler (缩放后特征)
        self.accuracies = {}
        self.is_trained = False
        self._records = []       # 训练用原始记录（用于预测时构建特征）

    def prepare_training_data(self, city_id: int):
        """准备训练数据：返回 X, y_high, y_low, records"""
        records = list(WeatherData.objects.filter(city_id=city_id).order_by('date'))
        if len(records) < max(LAG_DAYS) + 7:  # 至少 lag + 一点数据
            return None, None, None, None

        X, y_high, y_low = [], [], []
        start = max(LAG_DAYS)  # 从第7条开始（确保所有滞后可用）
        for i in range(start, len(records)):
            feats = _extract_features(records, i)
            X.append(feats)
            y_high.append(records[i].temperature_high)
            y_low.append(records[i].temperature_low)

        return np.array(X, dtype=np.float64), np.array(y_high), np.array(y_low), records

    def train_all(self, city_id: int) -> bool:
        """训练所有模型"""
        X, y_high, y_low, records = self.prepare_training_data(city_id)
        if X is None or len(X) < 14:
            return False

        self._records = records

        # 时间序列分割（80/20，保留顺序）
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_high_train, y_high_test = y_high[:split_idx], y_high[split_idx:]
        y_low_train, y_low_test = y_low[:split_idx], y_low[split_idx:]

        if len(X_test) < 3:
            return False

        for key, cfg in MODEL_REGISTRY.items():
            try:
                X_tr = X_train.copy()
                X_te = X_test.copy()

                # SVR 需要特征缩放
                if cfg['needs_scaling']:
                    scaler = StandardScaler()
                    X_tr = scaler.fit_transform(X_tr)
                    X_te = scaler.transform(X_te)
                    self.scalers[key] = scaler

                model_high = cfg['cls'](**cfg['params'])
                model_low = cfg['cls'](**cfg['params'])

                model_high.fit(X_tr, y_high_train)
                model_low.fit(X_tr, y_low_train)

                y_high_pred = model_high.predict(X_te)
                y_low_pred = model_low.predict(X_te)

                r2_high = max(0, r2_score(y_high_test, y_high_pred))
                r2_low = max(0, r2_score(y_low_test, y_low_pred))
                mae_high = mean_absolute_error(y_high_test, y_high_pred)
                mae_low = mean_absolute_error(y_low_test, y_low_pred)

                self.models[key] = {'high': model_high, 'low': model_low}
                self.accuracies[key] = {
                    'high': round(r2_high * 100, 1),
                    'low': round(r2_low * 100, 1),
                    'avg': round((r2_high + r2_low) / 2 * 100, 1),
                    'mae_high': round(mae_high, 1),
                    'mae_low': round(mae_low, 1),
                }
            except Exception as e:
                print(f"  模型 {cfg['name']} 训练失败: {e}")

        self.is_trained = len(self.models) > 0
        return self.is_trained

    def predict_all(self, city_id: int, days_ahead: int = 7) -> dict:
        """滚动预测未来N天（逐天递推，用预测值作为后续滞后特征）"""
        if not self.is_trained:
            self.train_all(city_id)
            if not self.is_trained:
                return {}

        # 取最近 N 天真实数据作为预测起点
        recent = self._records[-max(LAG_DAYS):]
        if len(recent) < max(LAG_DAYS):
            return {}

        today = datetime.now().date()
        predictions = {key: [] for key in self.models}

        for key, pair in self.models.items():
            model_high = pair['high']
            model_low = pair['low']
            scaler = self.scalers.get(key)
            predicted_so_far = []

            for i in range(1, days_ahead + 1):
                pred_date = today + timedelta(days=i)
                feats = _build_prediction_features(recent, pred_date, predicted_so_far)

                if scaler:
                    feats = scaler.transform(feats)

                high = round(float(model_high.predict(feats)[0]), 1)
                low = round(float(model_low.predict(feats)[0]), 1)

                # 物理约束：低温 ≤ 高温
                if low > high:
                    low, high = high, low

                predictions[key].append({
                    'date': pred_date.strftime('%Y-%m-%d'),
                    'high': high,
                    'low': low,
                })
                predicted_so_far.append((high, low))

        # 集成平均
        if len(self.models) >= 2:
            ensemble = []
            for i in range(days_ahead):
                highs = [preds[i]['high'] for preds in predictions.values() if i < len(preds)]
                lows = [preds[i]['low'] for preds in predictions.values() if i < len(preds)]
                if highs and lows:
                    ensemble.append({
                        'date': list(predictions.values())[0][i]['date'],
                        'high': round(sum(highs) / len(highs), 1),
                        'low': round(sum(lows) / len(lows), 1),
                    })
            if ensemble:
                predictions['ensemble'] = ensemble

        return predictions

    def get_all_accuracies(self) -> list:
        """获取所有模型准确度，按平均准确度降序"""
        result = []
        for key, cfg in MODEL_REGISTRY.items():
            if key in self.accuracies:
                acc = self.accuracies[key]
                result.append({
                    'key': key,
                    'name': cfg['name'],
                    'color': cfg['color'],
                    'high': acc['high'],
                    'low': acc['low'],
                    'avg': acc['avg'],
                    'mae_high': acc.get('mae_high', 0),
                    'mae_low': acc.get('mae_low', 0),
                })
        result.sort(key=lambda x: x['avg'], reverse=True)
        return result

    def get_best_model(self) -> str:
        acc = self.get_all_accuracies()
        return acc[0]['name'] if acc else '未知'


# 全局缓存
_predictor_cache: dict[int, MultiModelPredictor] = {}


def get_predictor(city_id: int) -> MultiModelPredictor:
    """获取或创建多模型预测器（带缓存）"""
    if city_id not in _predictor_cache:
        predictor = MultiModelPredictor()
        predictor.train_all(city_id)
        _predictor_cache[city_id] = predictor
    return _predictor_cache[city_id]


def batch_generate_predictions(province: str = None):
    """
    为所有（或指定省份的）城市生成7天预测并存入 PredictionResult
    每次调用先清除旧预测，再写入新预测
    """
    from apps.weather.models import City, PredictionResult

    cities = City.objects.filter(level__in=['city', 'district', 'town'])
    if province:
        cities = cities.filter(province=province)

    city_list = list(cities.order_by('id'))
    if not city_list:
        return 0

    today = datetime.now().date()
    total = 0

    # 清除旧预测（7天窗口内的）
    PredictionResult.objects.filter(
        predict_date__gte=today,
        predict_date__lte=today + timedelta(days=7),
    ).delete()

    for city in city_list:
        try:
            predictor = get_predictor(city.id)
            if not predictor.is_trained:
                continue
            accs = predictor.get_all_accuracies()
            best = accs[0]['name'] if accs else 'RandomForest'
            best_avg = accs[0]['avg'] if accs else 0

            predictions = predictor.predict_all(city.id, days_ahead=7)
            ens = predictions.get('ensemble', list(predictions.values())[0] if predictions else [])

            # 获取降水概率预报（Open-Meteo API）
            precip_map = {}  # date -> {prob, amount}
            try:
                import requests
                p_url = (
                    f'https://api.open-meteo.com/v1/forecast'
                    f'?latitude={city.latitude}&longitude={city.longitude}'
                    f'&daily=precipitation_sum,precipitation_probability_mean'
                    f'&forecast_days=7&timezone=Asia/Shanghai'
                )
                p_resp = requests.get(p_url, timeout=8)
                if p_resp.status_code == 200:
                    p_data = p_resp.json()
                    p_daily = p_data.get('daily', {})
                    p_dates = p_daily.get('time', [])
                    p_amounts = p_daily.get('precipitation_sum', [])
                    p_probs = p_daily.get('precipitation_probability_mean', [])
                    for idx, pd_str in enumerate(p_dates):
                        precip_map[pd_str] = {
                            'prob': int(p_probs[idx]) if idx < len(p_probs) and p_probs[idx] is not None else None,
                            'amount': round(float(p_amounts[idx]), 1) if idx < len(p_amounts) and p_amounts[idx] is not None else None,
                        }
            except Exception:
                pass

            objs = []
            for p in ens:
                pf = precip_map.get(p['date'], {})
                objs.append(PredictionResult(
                    city=city,
                    predict_date=p['date'],
                    predicted_high=p['high'],
                    predicted_low=p['low'],
                    predicted_condition='',
                    model_accuracy=best_avg,
                    model_name=best,
                    precip_probability=pf.get('prob'),
                    precip_amount=pf.get('amount'),
                ))
            PredictionResult.objects.bulk_create(objs)
            total += len(objs)
        except Exception as e:
            print(f'[预测] {city.name} 失败: {e}')

    return total
