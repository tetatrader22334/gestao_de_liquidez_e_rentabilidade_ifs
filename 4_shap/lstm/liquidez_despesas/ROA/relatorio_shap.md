# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_despesas/ROA/lstm_automl_ROA.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_despesas/ROA/preprocessadores_ROA.joblib`
- Target: `ROA`
- Instituição: `id_entidade`
- Tempo: `AnoMes_ord`
- Horizonte: `1`
- Comprimento da sequência: `8`
- Explainer: `permutation`
- Escala do output: `original do target`

## Amostras
- Dimensão da base: 615 linhas x 82 colunas
- Sequências reconstruídas: 503
- Sequências de background: 40
- Sequências explicadas: 80

## Top 15 variáveis agregadas
```
 rank                              feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1          despesas_adm_sobre_receitas                0.001067                        0.001024            -7.352765e-04
    2                          crise_covid                0.000819                        0.000531             3.807752e-04
    3                            crise_nme                0.000668                        0.000662             6.618035e-04
    4                              estatal                0.000593                        0.000521             1.540250e-04
    5                    liquidez_imediata                0.000574                        0.000510            -1.755969e-04
    6 operacoes_de_credito_sobre_captacoes                0.000494                        0.000465             4.077692e-07
    7          captacoes_sobre_ativo_total                0.000491                        0.000358             1.012660e-04
    8  provisao_sobre_operacoes_de_credito                0.000475                        0.000448             3.884652e-07
    9  depositos_a_prazo_sobre_ativo_total                0.000437                        0.000356             1.368708e-05
   10               indice_de_imobilizacao                0.000416                        0.000377             1.704014e-05
   11                             nsfr_dec                0.000365                        0.000337             6.663886e-05
   12     disponibilidades_sobre_depositos                0.000351                        0.000259             2.892664e-05
   13  depositos_a_vista_sobre_ativo_total                0.000344                        0.000274            -6.120545e-06
   14                 controle_estrangeiro                0.000315                        0.000289             2.443610e-04
   15               ativos_sobre_depositos                0.000231                        0.000181            -7.693534e-06
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1 t-2                    0.001066                0.000031
    2 t-1                    0.001052                0.000099
    3 t-4                    0.001014                0.000106
    4 t-3                    0.001014                0.000111
    5 t-7                    0.000953                0.000145
    6   t                    0.000933                0.000054
    7 t-5                    0.000923                0.000121
    8 t-6                    0.000906                0.000098
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

Tempo total de execução: 140.11 segundos.