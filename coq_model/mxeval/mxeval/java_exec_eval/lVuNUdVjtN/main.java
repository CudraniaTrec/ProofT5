import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class FlattenTuple{
  public static String flattenTuple(List<List<String>> testList){
    String result = "";
    for (List<String> stringList : testList){
      for (String string : stringList){
        result = result + string + " ";
      }
    }
    return result.trim();
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
        List<List<String>> arg00 = Arrays.asList(Arrays.asList("1", "4", "6"), Arrays.asList("5", "8"), Arrays.asList("2", "9"), Arrays.asList("1", "10"));
        String x0 = FlattenTuple.flattenTuple(Arrays.asList(Arrays.asList("1", "4", "6"), Arrays.asList("5", "8"), Arrays.asList("2", "9"), Arrays.asList("1", "10")));
        String v0 = "1 4 6 5 8 2 9 1 10";
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        List<List<String>> arg10 = Arrays.asList(Arrays.asList("2", "3", "4"), Arrays.asList("6", "9"), Arrays.asList("3", "2"), Arrays.asList("2", "11"));
        String x1 = FlattenTuple.flattenTuple(Arrays.asList(Arrays.asList("2", "3", "4"), Arrays.asList("6", "9"), Arrays.asList("3", "2"), Arrays.asList("2", "11")));
        String v1 = "2 3 4 6 9 3 2 2 11";
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        List<List<String>> arg20 = Arrays.asList(Arrays.asList("14", "21", "9"), Arrays.asList("24", "19"), Arrays.asList("12", "29"), Arrays.asList("23", "17"));
        String x2 = FlattenTuple.flattenTuple(Arrays.asList(Arrays.asList("14", "21", "9"), Arrays.asList("24", "19"), Arrays.asList("12", "29"), Arrays.asList("23", "17")));
        String v2 = "14 21 9 24 19 12 29 23 17";
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
