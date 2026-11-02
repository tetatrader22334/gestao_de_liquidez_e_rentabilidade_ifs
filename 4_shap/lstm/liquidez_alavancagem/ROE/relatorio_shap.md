# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_alavancagem/ROE/lstm_automl_ROE.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_alavancagem/ROE/preprocessadores_ROE.joblib`
- Target: `ROE`
- Instituição: `id_entidade`
- Tempo: `AnoMes_ord`
- Horizonte: `1`
- Comprimento da sequência: `6`
- Explainer: `permutation`
- Escala do output: `original do target`

## Amostras
- Dimensão da base: 615 linhas x 82 colunas
- Sequências reconstruídas: 531
- Sequências de background: 40
- Sequências explicadas: 80

## Top 15 variáveis agregadas
```
 rank                             feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1                         crise_covid                0.011860                        0.009187                 0.007150
    2              indice_de_basileia_dec                0.005346                        0.004730                 0.001429
    3       multiplicador_capital_proprio                0.005140                        0.004300                -0.000202
    4                           crise_nme                0.004356                        0.001800                 0.000864
    5                             estatal                0.004170                        0.004051                -0.000072
    6 depositos_a_vista_sobre_ativo_total                0.003725                        0.003568                 0.001115
    7 depositos_a_prazo_sobre_ativo_total                0.003676                        0.003420                -0.001112
    8              indice_de_imobilizacao                0.003324                        0.002967                -0.000083
    9                   liquidez_imediata                0.002985                        0.001624                 0.001211
   10         captacoes_sobre_ativo_total                0.002369                        0.001664                -0.001283
   11                            nsfr_dec                0.002210                        0.002076                -0.000043
   12                controle_estrangeiro                0.001924                        0.001831                 0.001038
   13              ativos_sobre_depositos                0.001567                        0.001124                -0.000853
   14                             lcr_dec                0.001172                        0.001017                -0.000188
   15    disponibilidades_sobre_depositos                0.001111                        0.000683                 0.000287
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1   t                    0.013561               -0.001443
    2 t-1                    0.010108                0.000263
    3 t-2                    0.008863                0.001910
    4 t-3                    0.008268                0.002565
    5 t-4                    0.007912                0.002938
    6 t-5                    0.007271                0.002955
```

## Arquivos gerados
- `shap_values_flat.npy`
- `shap_values_3d.npy`
- `shap_base_values.npy`
- `metadados_amostras_shap.csv`
- `shap_importance_lag_feature.csv`
- `shap_importance_feature_aggregated.csv`
- `shap_importance_by_lag.csv`
- `shap_bar_flat_top.png`
- `shap_beeswarm_flat_top.png`
- `shap_bar_feature_aggregated_top.png`
- `shap_heatmap_feature_lag_top.png`

Tempo total de execução: 81.68 segundos.