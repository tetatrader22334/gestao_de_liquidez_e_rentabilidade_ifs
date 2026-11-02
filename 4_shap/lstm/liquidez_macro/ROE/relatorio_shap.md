# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_macro/ROE/lstm_automl_ROE.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_macro/ROE/preprocessadores_ROE.joblib`
- Target: `ROE`
- Instituição: `id_entidade`
- Tempo: `AnoMes_ord`
- Horizonte: `1`
- Comprimento da sequência: `12`
- Explainer: `permutation`
- Escala do output: `original do target`

## Amostras
- Dimensão da base: 615 linhas x 82 colunas
- Sequências reconstruídas: 447
- Sequências de background: 40
- Sequências explicadas: 80

## Top 15 variáveis agregadas
```
 rank                             feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1                   pib_indice_sa_log                0.015900                        0.015362                 0.015362
    2                         crise_covid                0.006731                        0.004001                -0.000145
    3                             estatal                0.005115                        0.005101                 0.000303
    4              ipca_fim_trimestre_dec                0.004182                        0.001512                 0.001052
    5                           crise_nme                0.003334                        0.003328                 0.003328
    6 depositos_a_prazo_sobre_ativo_total                0.003291                        0.002777                -0.000875
    7             selic_fim_trimestre_dec                0.003001                        0.001549                -0.001422
    8 depositos_a_vista_sobre_ativo_total                0.002902                        0.002672                -0.000134
    9                   liquidez_imediata                0.002715                        0.001950                 0.000012
   10              indice_de_imobilizacao                0.002314                        0.002075                 0.001007
   11                            nsfr_dec                0.002288                        0.001768                -0.000401
   12                controle_estrangeiro                0.002087                        0.001844                 0.000410
   13         captacoes_sobre_ativo_total                0.001631                        0.001407                -0.000135
   14    disponibilidades_sobre_depositos                0.001456                        0.000639                 0.000112
   15                             lcr_dec                0.001420                        0.001115                 0.000223
```

## Importância por defasagem
```
 rank  lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1    t                    0.014553                0.007607
    2  t-1                    0.008562                0.002758
    3  t-2                    0.007328                0.002442
    4  t-3                    0.005802                0.001412
    5  t-4                    0.004845                0.001323
    6  t-5                    0.003994                0.000916
    7  t-6                    0.003497                0.000638
    8  t-7                    0.003019                0.000491
    9  t-8                    0.002722                0.000383
   10  t-9                    0.002465                0.000132
   11 t-10                    0.002292               -0.000045
   12 t-11                    0.001919               -0.000060
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

Tempo total de execução: 107.09 segundos.