class MaxSumList{
  public static List<int> maxSumList(List<List<int>> lists;){
    int maxSum = 0;
    List<int> list = new List<>();
    for (List<int> list1 : lists){
      int sum = 0;
      for (int i : list1){
        sum = sum + i;
      }
      if (sum > maxSum){
        maxSum = sum;
        list = new List<>();
        list.addAll(list1);
      } else {
        if (sum == maxSum){
          list.addAll(list1);
        }
      }
    }
    return list;
  }
}

class Main {
    public static boolean compare(Object obj1, Object obj2) {
        if (obj1 == null && obj2 == null){
            return true;
        } else if (obj1 == null || obj2 == null){
            return false;
        } else {
            return obj1.equals(obj2);
        }
    }
    
    public static void main(String[] args) throws Exception {
        List<List<Integer>> arg00 = Arrays.asList(Arrays.asList(1, 2, 3), Arrays.asList(4, 5, 6), Arrays.asList(10, 11, 12), Arrays.asList(7, 8, 9));
        List<Integer> x0 = MaxSumList.maxSumList(Arrays.asList(Arrays.asList(1, 2, 3), Arrays.asList(4, 5, 6), Arrays.asList(10, 11, 12), Arrays.asList(7, 8, 9)));
        List<Integer> v0 = Arrays.asList(10, 11, 12);
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        List<List<Integer>> arg10 = Arrays.asList(Arrays.asList(3, 2, 1), Arrays.asList(6, 5, 4), Arrays.asList(12, 11, 10));
        List<Integer> x1 = MaxSumList.maxSumList(Arrays.asList(Arrays.asList(3, 2, 1), Arrays.asList(6, 5, 4), Arrays.asList(12, 11, 10)));
        List<Integer> v1 = Arrays.asList(12, 11, 10);
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        List<List<Integer>> arg20 = Arrays.asList(Arrays.asList(2, 3, 1));
        List<Integer> x2 = MaxSumList.maxSumList(Arrays.asList(Arrays.asList(2, 3, 1)));
        List<Integer> v2 = Arrays.asList(2, 3, 1);
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
