# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_resultados/NIM/lstm_automl_NIM.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_resultados/NIM/preprocessadores_NIM.joblib`
- Target: `NIM`
- Instituição: `id_entidade`
- Tempo: `AnoMes_ord`
- Horizonte: `1`
- Comprimento da sequência: `4`
- Explainer: `permutation`
- Escala do output: `original do target`

## Amostras
- Dimensão da base: 615 linhas x 82 colunas
- Sequências reconstruídas: 559
- Sequências de background: 40
- Sequências explicadas: 80

## Top 15 variáveis agregadas
```
 rank                                                 feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1 resultado_de_intermediacao_financeira_sobre_ativo_total                0.014053                        0.010861                -0.004262
    2                    operacoes_de_credito_sobre_captacoes                0.006276                        0.002515                -0.000888
    3           resultado_de_provisao_pcddl_sobre_ativo_total                0.005955                        0.003082                -0.000193
    4                                             crise_covid                0.003967                        0.002655                 0.002089
    5                             captacoes_sobre_ativo_total                0.003937                        0.003451                -0.001911
    6                                                nsfr_dec                0.002688                        0.001886                 0.000881
    7                                                 lcr_dec                0.002544                        0.001609                -0.001039
    8                     depositos_a_prazo_sobre_ativo_total                0.002469                        0.001485                -0.000840
    9                                       liquidez_imediata                0.002065                        0.001211                 0.000251
   10                                  indice_de_imobilizacao                0.001786                        0.001734                -0.000388
   11                     depositos_a_vista_sobre_ativo_total                0.001689                        0.001362                 0.000675
   12                                  ativos_sobre_depositos                0.001149                        0.000869                -0.000479
   13                                               crise_nme                0.001119                        0.001073                 0.000949
   14                        disponibilidades_sobre_depositos                0.001042                        0.000688                 0.000432
   15                                                 estatal                0.000932                        0.000894                -0.000173
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1 t-3                    0.017289               -0.002735
    2 t-1                    0.012576               -0.002139
    3 t-2                    0.011495               -0.001830
    4   t                    0.010604                0.001917
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

Tempo total de execução: 159.74 segundos.