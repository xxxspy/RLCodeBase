function main()
  load RQ1.out;
  load JQTP1.out;
  load AS1.out;
  load MILP1.out;
  load MILP-POLICY1.out;
  load MILP-QI1.out;
  load MILP-QI-POLICY1.out;
  load OPT-POLICY1.out;

  len = 3;
  op = mean(OPT_POLICY1)
  e = mean(JQTP1)
  piqi = mean(MILP_QI_POLICY1)
  pi = mean(MILP_POLICY1)
  milpqi = mean(MILP_QI1)
  milp = mean(MILP1)
  as = mean(AS1)
  rq = mean(RQ1)

  keyboard

  %as3 = mean(AS3)
  %as5 = mean(AS5)
  %milp3 = mean(MILP3)
  %milp5 = mean(MILP5)

  plot(x, ones(1, len) * e(1), '*-');
  hold on;
  plot(x, [milp(1), milp3(1), milp5(1)], '+-');
  plot(x, [as(1), as3(1), as5(1)], '+--');
  plot(x, ones(1, len) * rq(1), 'o-');
  legend('Exhaustive', 'Query Projection', 'Active Sampling', 'Random Query');
  xlabel('# of Queries to Compute EVOI');
  ylabel('Q-Value');
 
  figure;
  plot(x, ones(1, len) * e(2), '*-');
  hold on;
  plot(x, [milp(2), milp3(2), milp5(2)], '+-');
  plot(x, [as(2), as3(2), as5(2)], '+--');
  plot(x, ones(1, len) * rq(2), 'o-');
  legend('Exhaustive', 'Query Projection', 'Active Sampling', 'Random Query');
  xlabel('# of Queries to Compute EVOI');
  ylabel('Computation Time (sec.)');
end

function [m, ci] = process(data)
  n = size(data, 1);
  m = mean(data);
  ci = 1.96 * std(data) / sqrt(n);
end

