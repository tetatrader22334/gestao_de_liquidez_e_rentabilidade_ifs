# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_resultados/ROA/lstm_automl_ROA.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_resultados/ROA/preprocessadores_ROA.joblib`
- Target: `ROA`
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
 rank                                                 feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1           resultado_de_provisao_pcddl_sobre_ativo_total                0.001211                        0.000729            -8.022501e-07
    2 resultado_de_intermediacao_financeira_sobre_ativo_total                0.001033                        0.000855            -2.980381e-04
    3                                             crise_covid                0.001033                        0.000462             8.028478e-05
    4                                                 estatal                0.000855                        0.000855            -4.446123e-06
    5                                               crise_nme                0.000756                        0.000240             2.335505e-04
    6                     depositos_a_prazo_sobre_ativo_total                0.000734                        0.000489            -2.443185e-04
    7                    operacoes_de_credito_sobre_captacoes                0.000644                        0.000136            -5.110077e-05
    8                             captacoes_sobre_ativo_total                0.000619                        0.000616            -2.594028e-04
    9                                       liquidez_imediata                0.000547                        0.000125             4.131858e-05
   10                     depositos_a_vista_sobre_ativo_total                0.000435                        0.000208            -1.183716e-04
   11                        disponibilidades_sobre_depositos                0.000420                        0.000124            -6.711264e-06
   12                                    controle_estrangeiro                0.000379                        0.000376             1.270621e-04
   13                                  indice_de_imobilizacao                0.000352                        0.000344            -4.756971e-05
   14                                  ativos_sobre_depositos                0.000305                        0.000184            -1.543413e-04
   15                                                nsfr_dec                0.000283                        0.000246            -1.235559e-05
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1   t                    0.002685               -0.000116
    2 t-5                    0.002553               -0.000175
    3 t-1                    0.001363               -0.000199
    4 t-3                    0.001183               -0.000001
    5 t-4                    0.001050               -0.000063
    6 t-2                    0.000981               -0.000169
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

Tempo total de execução: 175.42 segundos.